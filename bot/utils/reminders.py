"""Reminders scheduler: polls DB for due reminders and sends messages to chat."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from aiogram import Bot

from bot.utils.db import get_conn
from bot.utils.log import logger
from bot.utils.openai import OpenAIClient


@dataclass
class Reminder:
    id: int
    chat_id: int
    user_id: int
    text: str
    due_at: str  # UTC in '%Y-%m-%d %H:%M:%S'
    silent: bool


async def _fetch_due(limit: int = 5) -> List[Reminder]:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with get_conn() as db:
        cur = await db.execute(
            """
            SELECT id, chat_id, user_id, text, due_at, silent
            FROM reminders
            WHERE status = 'scheduled' AND due_at <= ?
            ORDER BY due_at ASC
            LIMIT ?
            """,
            (now_utc, limit),
        )
        rows = await cur.fetchall()
    return [Reminder(id=r[0], chat_id=r[1], user_id=r[2], text=r[3], due_at=r[4], silent=bool(r[5])) for r in rows]


async def _mark_status(reminder_id: int, status: str) -> None:
    async with get_conn() as db:
        if status == "done":
            await db.execute(
                "UPDATE reminders SET status='done', executed_at=CURRENT_TIMESTAMP WHERE id=?",
                (reminder_id,),
            )
        else:
            await db.execute(
                "UPDATE reminders SET status=?, executed_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, reminder_id),
            )
        await db.commit()


async def _handle_one(bot: Bot, r: Reminder) -> None:
    """Формирует текст уведомления через модель и отправляет его пользователю."""
    try:
        # Формируем краткий запрос к модели на основе напоминания
        dt_utc = r.due_at  # строка в UTC '%Y-%m-%d %H:%M:%S'
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

        # Отправляем ответ модели
        await bot.send_message(r.chat_id, response_text, disable_notification=r.silent)
        await _mark_status(r.id, "done")
    except Exception as e:
        logger.error(f"reminder {r.id} handling failed: {e}")
        # Фолбэк: старое поведение (не блокируем остальные напоминания)
        try:
            text = f"🔔 Напоминание: {r.text}" if not r.text.lower().startswith("напоминание") else r.text
            await bot.send_message(r.chat_id, text, disable_notification=r.silent)
            await _mark_status(r.id, "done")
        except Exception:
            try:
                await _mark_status(r.id, "error")
            except Exception:
                pass


def start_reminders_scheduler(bot: Bot) -> asyncio.Task:
    stop_event = asyncio.Event()

    async def _loop():
        logger.info("⏰ Reminders scheduler started")
        try:
            while not stop_event.is_set():
                try:
                    due = await _fetch_due(limit=5)
                    for r in due:
                        await _handle_one(bot, r)
                except Exception as e:
                    logger.warning(f"reminders loop warn: {e}")
                # Пауза между итерациями
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    pass
        finally:
            logger.info("⏹ Reminders scheduler stopped")

    task = asyncio.create_task(_loop(), name="reminders_scheduler")
    # Помечаем стоп-событие для корректной остановки снаружи
    setattr(task, "_gpttg_stop_event", stop_event)
    return task
