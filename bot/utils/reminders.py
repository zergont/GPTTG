"""Reminders scheduler: polls DB for due reminders and sends messages to chat."""
from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from aiogram import Bot

from bot.utils.db import get_conn
from bot.utils.log import logger
from bot.utils.openai import OpenAIClient
from bot.config import settings


STALE_PICK_SECONDS = 60  # если picked_at старше — считаем задачу «осиротевшей»


@dataclass
class Reminder:
    id: int
    chat_id: int
    user_id: int
    text: str
    due_at: str  # UTC in '%Y-%m-%d %H:%M:%S'
    silent: bool
    idempotency_key: Optional[str] = None
    meta_json: Optional[str] = None


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


async def _fetch_due(limit: int) -> List[Reminder]:
    # lookahead и анти-дрейф, исключаем недавно взятые задачи
    now = datetime.now(timezone.utc)
    now_plus = now + timedelta(seconds=settings.reminder_lookahead_seconds)
    stale_limit = (now - timedelta(seconds=STALE_PICK_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    now_plus_str = now_plus.strftime("%Y-%m-%d %H:%M:%S")
    async with get_conn() as db:
        cur = await db.execute(
            """
            SELECT id, chat_id, user_id, text, due_at, silent, idempotency_key, meta_json
            FROM reminders
            WHERE status = 'scheduled'
              AND due_at <= ?
              AND (picked_at IS NULL OR picked_at <= ?)
            ORDER BY due_at ASC
            LIMIT ?
            """,
            (now_plus_str, stale_limit, limit),
        )
        rows = await cur.fetchall()
    return [
        Reminder(
            id=r[0], chat_id=r[1], user_id=r[2], text=r[3], due_at=r[4], silent=bool(r[5]),
            idempotency_key=r[6], meta_json=r[7]
        ) for r in rows
    ]


async def _mark_status(reminder_id: int, status: str) -> None:
    async with get_conn() as db:
        if status == "done":
            await db.execute(
                "UPDATE reminders SET status='done', executed_at=CURRENT_TIMESTAMP, fired_at=CURRENT_TIMESTAMP WHERE id=?",
                (reminder_id,),
            )
        else:
            await db.execute(
                "UPDATE reminders SET status=?, executed_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, reminder_id),
            )
        await db.commit()


async def _claim(reminder_id: int) -> bool:
    """Атомарно отмечает задачу как взятую воркером, чтобы избежать гонок (single process — защита от дублей)."""
    async with get_conn() as db:
        await db.execute(
            """
            UPDATE reminders
               SET picked_at=CURRENT_TIMESTAMP
             WHERE id=? AND (picked_at IS NULL OR picked_at <= DATETIME('now', ?))
            """,
            (reminder_id, f'-{STALE_PICK_SECONDS} seconds'),
        )
        await db.commit()
        cur = await db.execute("SELECT picked_at FROM reminders WHERE id=?", (reminder_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


def _build_idempotency_key(r: Reminder) -> str:
    base = f"rem_{r.id}:{r.chat_id}:{r.user_id}:{r.due_at}"
    return base


def _next_reminder_params(meta: Optional[str]) -> Optional[Tuple[datetime, dict]]:
    if not meta:
        return None
    try:
        obj = json.loads(meta)
        steps_left = obj.get("steps_left")
        end_at = obj.get("end_at")
        next_at = obj.get("next_at")
        next_offset = obj.get("next_offset")
        if steps_left is not None and steps_left <= 0:
            return None
        if end_at:
            try:
                end_dt = _parse_dt(end_at)
            except Exception:
                end_dt = None
        else:
            end_dt = None
        if next_at:
            try:
                due = _parse_dt(next_at)
            except Exception:
                due = None
        else:
            due = None
        if due is None and next_offset:
            try:
                # next_offset в секундах
                due = datetime.now(timezone.utc) + timedelta(seconds=int(next_offset))
            except Exception:
                return None
        if due is None:
            return None
        if end_dt and due > end_dt:
            return None
        # уменьшаем шаги
        if steps_left is not None:
            obj["steps_left"] = int(steps_left) - 1
        # очистим next_at, чтобы не тащить фиксированную дату дальше, если использовался offset
        obj.pop("next_at", None)
        return due, obj
    except Exception:
        return None


async def _spawn_next_if_needed(r: Reminder) -> None:
    nxt = _next_reminder_params(r.meta_json)
    if not nxt:
        return
    due_dt, new_meta = nxt
    due_str = due_dt.strftime("%Y-%m-%d %H:%M:%S")
    # Наследуем silent из meta, если задан, иначе из текущего
    try:
        meta_silent = json.loads(r.meta_json).get("silent") if r.meta_json else None
    except Exception:
        meta_silent = None
    silent = int(meta_silent if meta_silent is not None else r.silent)
    async with get_conn() as db:
        await db.execute(
            """
            INSERT INTO reminders(chat_id, user_id, text, due_at, silent, status, meta_json)
            VALUES(?, ?, ?, ?, ?, 'scheduled', ?)
            """,
            (r.chat_id, r.user_id, r.text, due_str, silent, json.dumps(new_meta, ensure_ascii=False)),
        )
        await db.commit()
    logger.info(f"[reminders] chained next created for chat={r.chat_id} user={r.user_id} due_at={due_str}")


async def _handle_one(bot: Bot, r: Reminder) -> None:
    """Формирует текст уведомления через модель и отправляет его пользователю."""
    # идемпотентность на уровне ключа (локально)
    idemp = r.idempotency_key or _build_idempotency_key(r)
    try:
        # Блокируем задачу (single-process), чтобы не схватили параллельно
        if not await _claim(r.id):
            return

        # Джиттер ±settings.reminder_jitter_seconds
        jitter = settings.reminder_jitter_seconds
        if jitter > 0:
            shift = random.uniform(-jitter, jitter)
            await asyncio.sleep(max(0.0, shift))

        # Формируем краткий запрос к модели на основе напоминания
        dt_utc = r.due_at
        instruction = (
            "Сформируй одно короткое уведомление по сработавшему напоминанию. "
            "Сообщение должно быть лаконичным и понятным. Если уместно, можешь добавить полезный контекст (например, краткую сводку погоды, дорожную ситуацию, время), но избегай лишней болтовни."
        )
        user_msg = f"Напоминание: {r.text}. Сработало сейчас (UTC {dt_utc})."
        content = [{
            "type": "message",
            "role": "user",
            "content": f"{instruction}\n\n{user_msg}"
        }]

        # Просим модель; отключаем инструменты напоминаний, можно оставить web_search=auto
        response_text = await OpenAIClient.responses_request(
            r.chat_id,
            r.user_id,
            content,
            previous_response_id=None,
            enable_web_search=True,
            include_reminder_tools=False,
        )

        # Идемпотентная попытка отправки: записываем ключ перед send
        async with get_conn() as db:
            await db.execute(
                "UPDATE reminders SET idempotency_key=? WHERE id=? AND idempotency_key IS NULL",
                (idemp, r.id),
            )
            await db.commit()

        # Отправляем
        await bot.send_message(r.chat_id, response_text, disable_notification=r.silent)

        # Помечаем статус и fired_at
        await _mark_status(r.id, "done")
        fired_at = _utcnow_str()
        logger.info(f"[reminders] sent id={r.id} chat={r.chat_id} user={r.user_id} fired_at_utc={fired_at}")

        # Чейним следующий, если нужно
        await _spawn_next_if_needed(r)

    except Exception as e:
        logger.error(f"reminder {r.id} handling failed: {e}")
        # Фолбэк: не блокируем остальные напоминания
        try:
            text = f"🔔 Напоминание: {r.text}" if not r.text.lower().startswith("напоминание") else r.text
            await bot.send_message(r.chat_id, text, disable_notification=r.silent)
            await _mark_status(r.id, "done")
        except Exception:
            try:
                await _mark_status(r.id, "error")
            except Exception:
                pass


# ------------------------
# Self-calls (assistant scheduled self messages)
# ------------------------

@dataclass
class SelfCall:
    id: int
    chat_id: int
    user_id: int
    due_at: str  # UTC '%Y-%m-%d %H:%M:%S'
    topic: Optional[str]
    payload_json: Optional[str]


async def _self_fetch_due(limit: int) -> List[SelfCall]:
    now = datetime.now(timezone.utc)
    now_plus = now + timedelta(seconds=settings.reminder_lookahead_seconds)
    stale_limit = (now - timedelta(seconds=STALE_PICK_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    now_plus_str = now_plus.strftime("%Y-%m-%d %H:%M:%S")
    async with get_conn() as db:
        cur = await db.execute(
            """
            SELECT id, chat_id, user_id, due_at, topic, payload_json
              FROM self_calls
             WHERE status='scheduled'
               AND due_at <= ?
               AND (picked_at IS NULL OR picked_at <= ?)
             ORDER BY due_at ASC
             LIMIT ?
            """,
            (now_plus_str, stale_limit, limit),
        )
        rows = await cur.fetchall()
    return [SelfCall(id=r[0], chat_id=r[1], user_id=r[2], due_at=r[3], topic=r[4], payload_json=r[5]) for r in rows]


async def _self_claim(id_: int) -> bool:
    async with get_conn() as db:
        await db.execute(
            """
            UPDATE self_calls
               SET picked_at=CURRENT_TIMESTAMP
             WHERE id=? AND (picked_at IS NULL OR picked_at <= DATETIME('now', ?))
            """,
            (id_, f'-{STALE_PICK_SECONDS} seconds'),
        )
        await db.commit()
        cur = await db.execute("SELECT picked_at FROM self_calls WHERE id=?", (id_,))
        row = await cur.fetchone()
        return bool(row and row[0])


async def _self_mark_status(id_: int, status: str) -> None:
    async with get_conn() as db:
        if status == 'done':
            await db.execute(
                "UPDATE self_calls SET status='done', executed_at=CURRENT_TIMESTAMP, fired_at=CURRENT_TIMESTAMP WHERE id=?",
                (id_,),
            )
        else:
            await db.execute(
                "UPDATE self_calls SET status=?, executed_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, id_),
            )
        await db.commit()


def _extract_next_self_call(text: str) -> Optional[Tuple[datetime, Optional[str], Optional[dict]]]:
    """Парсит из ответа ассистента инструкцию следующего самовызова.
    Формат: в конце сообщения отдельной строкой JSON-маркер: 
    <!--self_call:{"in":"5m","topic":"forex","payload":{...}}-->
    Либо абсолютное время: {"at":"2025-08-20 12:00:00"} (UTC)
    """
    try:
        marker_start = text.rfind("<!--self_call:")
        if marker_start == -1:
            return None
        marker_end = text.find("-->", marker_start)
        if marker_end == -1:
            return None
        payload = text[marker_start + len("<!--self_call:"):marker_end].strip()
        obj = json.loads(payload)
        when = obj.get("in") or obj.get("at")
        topic = obj.get("topic")
        payload_obj = obj.get("payload") if isinstance(obj.get("payload"), dict) else None
        if not when:
            return None
        if isinstance(when, str) and when.lower().startswith("in "):
            # относительное "in 5m/2h/1d"
            total_seconds = 0
            for amount, unit in re.findall(r"(\d+)\s*([smhd])", when.lower()):
                v = int(amount)
                if unit == 's':
                    total_seconds += v
                elif unit == 'm':
                    total_seconds += v * 60
                elif unit == 'h':
                    total_seconds += v * 3600
                elif unit == 'd':
                    total_seconds += v * 86400
            if total_seconds <= 0:
                return None
            due = datetime.now(timezone.utc) + timedelta(seconds=total_seconds)
        else:
            # абсолют UTC 'YYYY-MM-DD HH:MM:SS'
            try:
                due = datetime.strptime(str(when), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return due, topic, payload_obj
    except Exception:
        return None


async def _self_handle_one(bot: Bot, sc: SelfCall) -> None:
    try:
        if not await _self_claim(sc.id):
            return
        # Формируем запрос к модели: тема + произвольный payload
        instr = (
            "Это отложенный самовызов ассистента. Сформируй одно содержательное сообщение для пользователя по теме, "
            "которую ты считаешь актуальной на текущий момент на основе контекста темы/пейлоада. Ты можешь свободно вести беседу. "
            "Если хочешь продолжить беседу позже, добавь в конце сообщения JSON-маркер в HTML-комментарии, например: \n"
            "<!--self_call:{\"in\":\"in 30m\",\"topic\":\"forex\"}}-->" 
        )
        payload_text = sc.payload_json or "{}"
        content = [{
            "type": "message",
            "role": "user",
            "content": f"{instr}\n\nТема: {sc.topic or '-'}\nPayload: {payload_text}"
        }]
        # Берём previous_response_id из истории
        prev_id = None
        async with get_conn() as db:
            cur = await db.execute("SELECT last_response FROM chat_history WHERE chat_id=?", (sc.chat_id,))
            row = await cur.fetchone()
            prev_id = row[0] if row else None
        text = await OpenAIClient.responses_request(
            sc.chat_id, sc.user_id, content, previous_response_id=prev_id, enable_web_search=True, include_reminder_tools=False
        )
        await bot.send_message(sc.chat_id, text)
        await _self_mark_status(sc.id, 'done')
        # Спарсить следующий самовызов
        nxt = _extract_next_self_call(text)
        if nxt:
            due, topic, payload = nxt
            async with get_conn() as db:
                await db.execute(
                    "INSERT INTO self_calls(chat_id, user_id, due_at, topic, payload_json, status) VALUES(?,?,?,?,?, 'scheduled')",
                    (sc.chat_id, sc.user_id, due.strftime("%Y-%m-%d %H:%M:%S"), topic, json.dumps(payload or {}, ensure_ascii=False)),
                )
                await db.commit()
            logger.info(f"[self_calls] scheduled next for chat={sc.chat_id} at {due}")
    except Exception as e:
        logger.warning(f"self_call {sc.id} handling failed: {e}")
        try:
            await _self_mark_status(sc.id, 'error')
        except Exception:
            pass


def start_self_calls_scheduler(bot: Bot) -> asyncio.Task:
    stop_event = asyncio.Event()

    async def _loop():
        logger.info("🤖 Self-calls scheduler started")
        try:
            while not stop_event.is_set():
                try:
                    due = await _self_fetch_due(limit=max(1, settings.reminder_batch_limit))
                    for sc in due:
                        await _self_handle_one(bot, sc)
                except Exception as e:
                    logger.debug(f"self_calls loop warn: {e}")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=float(settings.reminder_poll_interval_seconds))
                except asyncio.TimeoutError:
                    pass
        finally:
            logger.info("⏹ Self-calls scheduler stopped")

    task = asyncio.create_task(_loop(), name="self_calls_scheduler")
    setattr(task, "_gpttg_stop_event", stop_event)
    return task


# ------------------------
# Reminders scheduler main entry
# ------------------------

def start_reminders_scheduler(bot: Bot) -> asyncio.Task:
    stop_event = asyncio.Event()

    async def _loop():
        logger.info("⏰ Reminders scheduler started")
        sent = skipped = failed = 0
        lag_sum = 0.0
        lag_count = 0
        try:
            while not stop_event.is_set():
                try:
                    batch_limit = max(1, settings.reminder_batch_limit)
                    due = await _fetch_due(limit=batch_limit)
                    if not due:
                        skipped += 1
                    now = datetime.now(timezone.utc)
                    for r in due:
                        try:
                            lag = max(0.0, (now - _parse_dt(r.due_at)).total_seconds())
                            lag_sum += lag
                            lag_count += 1
                        except Exception:
                            pass
                        await _handle_one(bot, r)
                        sent += 1
                except Exception as e:
                    logger.warning(f"reminders loop warn: {e}")
                    failed += 1
                # Пауза между итерациями
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=float(settings.reminder_poll_interval_seconds))
                except asyncio.TimeoutError:
                    pass
        finally:
            avg_lag = (lag_sum / lag_count) if lag_count else 0.0
            logger.info(f"⏹ Reminders scheduler stopped (sent={sent}, skipped={skipped}, failed={failed}, avg_lag_s={avg_lag:.2f})")

    task = asyncio.create_task(_loop(), name="reminders_scheduler")
    # Помечаем стоп-событие для корректной остановки снаружи
    setattr(task, "_gpttg_stop_event", stop_event)
    return task
