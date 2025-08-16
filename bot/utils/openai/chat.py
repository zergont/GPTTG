"""Чат с использованием OpenAI Responses API."""
from typing import Any, Dict, List
import re
import json
from datetime import datetime, timezone, timedelta
import openai

from bot.config import settings
from bot.utils.db import get_conn
from bot.utils.log import logger
from .base import client, oai_limiter
from .models import ModelsManager


class ChatManager:
    """Управление чатом через OpenAI Responses API."""

    # Поддерживаем закрытие блоков тремя или четырьмя бэктиками (модель иногда копирует пример буквально)
    REMINDER_FENCE_RE = re.compile(r"```\s*reminder\s*\n([\s\S]*?)\n```+", re.IGNORECASE)

    @staticmethod
    async def responses_request(
        chat_id: int,
        user_id: int,
        user_content: List[Dict[str, Any]],
        previous_response_id: str | None = None,
        tools: list | None = None,
        enable_web_search: bool | None = None,
        tool_choice: str | None = None
    ) -> str:
        """
        Отправляет запрос в OpenAI Responses API.

        Args:
            chat_id: ID чата.
            user_id: ID пользователя (для корректной статистики).
            user_content: Список сообщений для контекста.
            previous_response_id: ID предыдущего ответа (для сохранения контекста).
            tools: Список инструментов.
            enable_web_search: Включить web_search tool.
            tool_choice: Выбор инструмента (auto/none/required).

        Returns:
            str: Ответ от OpenAI.
        Поддерживает скрытый блок напоминания в конце ответа ассистента с форматом:
        ```reminder
        {"when": "in 5m" | ISO8601, "text": "...", "silent": false}
        ```
        Блок удаляется из видимого ответа и сохраняется одноразовое напоминание в БД.
        """
        async with oai_limiter(chat_id):
            logger.info("Запрос в OpenAI (chat=%s, prev=%s)", chat_id, previous_response_id)

            current_model = await ModelsManager.get_current_model()

            if previous_response_id is None:
                async with get_conn() as db:
                    cur = await db.execute(
                        "SELECT last_response FROM chat_history WHERE chat_id = ?",
                        (chat_id,)
                    )
                    row = await cur.fetchone()
                    previous_response_id = row[0] if row else None

            input_content: List[Dict[str, Any]] = []

            # Базовый системный промпт и инструкции по напоминаниям
            reminder_instr = (
                "\n\nИнструкция по напоминаниям (без инструментов):\n"
                "• Если уместно или пользователь просит, в конце ответа добавь один скрытый блок напоминания.\n"
                "• Формат: три бэктика и слово reminder на первой строке, JSON на следующей, затем закрывающие три бэктика.\n"
                "Пример:\n```reminder\n{\"when\": \"in 45m\", \"text\": \"…\", \"silent\": false}\n```\n"
                "• when: ISO8601 с часовым поясом (2025-08-13T22:30:00+03:00) или относительное 'in X' (in 45m, in 2h 30m, in 1d).\n"
                "• text: кратко, до 200 символов, без префикса 'Напоминание:'.\n"
                "• silent: необязателен, по умолчанию false.\n"
                "• Блок не должен попадать в видимый ответ пользователю.\n"
            )

            if previous_response_id is None:
                # Первый запрос в чате — полный системный промпт с инструкцией по напоминаниям
                input_content.append({
                    "type": "message",
                    "content": settings.system_prompt + reminder_instr,
                    "role": "system",
                })
                logger.info(f"Добавлен системный промпт для первого запроса в чате {chat_id}")
            else:
                # В последующих запросах добавляем краткое напоминание-инструкцию,
                # чтобы модель стабильно эмитила блок "reminder" при необходимости.
                input_content.append({
                    "type": "message",
                    "content": (
                        "Если пользователь просит запланировать напоминание, в конце ответа добавь скрытый блок "
                        "```reminder {\"when\": \"in 5m\"|ISO8601, \"text\": \"...\", \"silent\": false}```. "
                        "Не показывай этот блок пользователю."
                    ),
                    "role": "system",
                })
                logger.info(f"Используется previous_response_id={previous_response_id}, системный промпт сокращён")

            # Добавляем пользовательский ввод
            input_content.extend(user_content)

            request_params: Dict[str, Any] = {
                "model": current_model,
                "input": input_content,
                "previous_response_id": previous_response_id,
                "store": True,
            }

            # Инструменты (только web_search)
            use_web = True if enable_web_search is None else bool(enable_web_search)
            if use_web:
                request_params.setdefault("tools", []).append({"type": "web_search"})
            if tools:
                request_params.setdefault("tools", []).extend(tools)
            if tool_choice:
                request_params["tool_choice"] = tool_choice

            if getattr(settings, "debug_mode", False):
                logger.debug(f"[DEBUG] OpenAI REQUEST: {request_params}")

            try:
                response = await client.responses.create(**request_params)
            except openai.APITimeoutError:
                logger.error("OpenAI: превышено время ожидания ответа")
                return "⏳ Превышено время ожидания ответа. Попробуйте еще раз."
            except openai.RateLimitError as e:
                logger.error("OpenAI: превышен лимит запросов")
                remaining_tokens = "неизвестно"
                reset_time = "неизвестно"
                if hasattr(e, 'response') and e.response:
                    headers = getattr(e.response, 'headers', {})
                    remaining_tokens = headers.get('x-ratelimit-remaining-tokens', 'неизвестно')
                    reset_time = headers.get('x-ratelimit-reset-tokens', 'неизвестно')
                return (
                    f"⏳ <b>Превышен лимит токенов OpenAI</b>\n\n"
                    f"🔢 Осталось токенов: <code>{remaining_tokens}</code>\n"
                    f"🕒 Сброс через: <code>{reset_time}</code> сек\n\n"
                    f"💡 Рекомендации:\n"
                    f"• /setmodel → gpt-4o-mini (дешевле)\n"
                    f"• Подождите {reset_time} секунд\n"
                    f"• Упростите запрос"
                )
            except (openai.PermissionDeniedError, openai.BadRequestError) as e:
                error_message = str(e)
                logger.warning(f"Проблема с моделью {current_model}: {error_message}")
                from .models import ModelsManager as _MM
                await _MM.set_current_model("gpt-4o-mini")
                if "does not have access" in error_message:
                    return f"❌ Нет доступа к модели {current_model}. Модель изменена на gpt-4o-mini. Повторите запрос."
                elif "not supported with the Responses API" in error_message:
                    return f"❌ Модель {current_model} не поддерживает Responses API. Модель изменена на gpt-4o-mini. Повторите запрос."
                elif "does not support image inputs" in error_message:
                    return f"❌ Модель {current_model} не поддерживает изображения. Модель изменена на gpt-4o-mini. Повторите запрос."
                else:
                    return f"❌ Проблема с моделью {current_model}. Модель изменена на gpt-4o-mini. Повторите запрос."
            except Exception as e:
                logger.error(f"OpenAI:unexpected error: {e}")
                return f"❌ Произошла неожиданная ошибка: {str(e)[:100]}..."

            if getattr(settings, "debug_mode", False):
                logger.debug(f"[DEBUG] OpenAI RESPONSE: {response}")

            usage = getattr(response, "usage", None)
            total_tokens = getattr(usage, "total_tokens", 0) if usage else 0

            # Стоимость: учитываем цены модели и cached_input, если есть
            prices = ModelsManager.get_model_prices(getattr(response, "model", None) or current_model)
            in_price = prices.get("input", settings.openai_price_per_1k_tokens)
            out_price = prices.get("output", settings.openai_price_per_1k_tokens)
            cached_price = prices.get("cached_input", in_price)

            # Попытаться взять раздельные счётчики токенов
            input_tokens = (
                getattr(usage, "prompt_tokens", None)
                or getattr(usage, "input_tokens", None)
            )
            output_tokens = (
                getattr(usage, "completion_tokens", None)
                or getattr(usage, "output_tokens", None)
            )
            cached_input_tokens = (
                getattr(usage, "cached_prompt_tokens", None)
                or getattr(usage, "cached_input_tokens", None)
            )

            if input_tokens is not None and output_tokens is not None:
                # Разделяем на закешированные и обычные входные токены
                cached_t = max(0, int(cached_input_tokens)) if cached_input_tokens is not None else 0
                regular_t = max(0, int(input_tokens) - cached_t)
                cost = (regular_t / 1000.0) * in_price + (cached_t / 1000.0) * cached_price + (int(output_tokens) / 1000.0) * out_price
            else:
                # Fallback: считаем по total и глобальной цене
                cost = total_tokens / 1000.0 * settings.openai_price_per_1k_tokens

            # Извлекаем полный текст ответа ассистента
            full_text = ""
            if getattr(response, "output", None):
                try:
                    parts: List[str] = []
                    for message in response.output:
                        if hasattr(message, 'content') and message.content:
                            for content_item in message.content:
                                # Новый SDK может представлять текст как type=output_text
                                if getattr(content_item, 'type', '') == 'output_text' and hasattr(content_item, 'text') and content_item.text:
                                    parts.append(content_item.text)
                                # Совместимость
                                elif hasattr(content_item, 'text') and content_item.text:
                                    parts.append(content_item.text)
                    full_text = "\n".join(parts).strip()
                except Exception as e:
                    logger.error(f"Ошибка при сборке текста ответа: {e}")

            if not full_text:
                logger.warning("Не удалось извлечь текст из ответа OpenAI")
                visible_text = "Извините, не удалось обработать ответ. Попробуйте еще раз."
                reminder_ack = None
            else:
                # Вырезаем скрытый reminder-блок(и) и парсим последний
                visible_text, reminder_ack = await ChatManager._extract_and_schedule_reminder(full_text, chat_id, user_id)

            # Сохраняем метрики и last_response
            async with get_conn() as db:
                await db.execute(
                    "REPLACE INTO chat_history(chat_id, last_response) VALUES (?, ?)",
                    (chat_id, response.id),
                )
                await db.execute(
                    "INSERT INTO usage(chat_id, user_id, tokens, cost, model) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, user_id, total_tokens, cost, getattr(response, "model", current_model)),
                )
                await db.commit()

            # Формируем финальный текст для пользователя
            if reminder_ack:
                if visible_text:
                    return f"{visible_text}\n\n{reminder_ack}"
                return reminder_ack
            return visible_text

    @staticmethod
    async def _extract_and_schedule_reminder(text: str, chat_id: int, user_id: int) -> tuple[str, str | None]:
        """Ищет в тексте скрытые блоки ```reminder ...```, удаляет их из видимого текста,
        парсит последний блок и при валидности создаёт напоминание. Возвращает (visible_text, ack|None).
        """
        matches = list(ChatManager.REMINDER_FENCE_RE.finditer(text))
        if not matches:
            # fallback: распарсить русскую фразу «напомнить/напоминание … через X»
            visible_text = text.strip()
            fallback = ChatManager._try_parse_ru_reminder_from_text(visible_text)
            if not fallback:
                return visible_text, None
            reminder_text, due_at_utc, silent = fallback
            try:
                async with get_conn() as db:
                    cur = await db.execute(
                        "INSERT INTO reminders(chat_id, user_id, text, due_at, silent, status) VALUES (?, ?, ?, ?, ?, 'scheduled')",
                        (chat_id, user_id, reminder_text[:200], due_at_utc.strftime("%Y-%m-%d %H:%M:%S"), int(silent)),
                    )
                    await db.commit()
                    reminder_id = getattr(cur, 'lastrowid', None)
                human_time = due_at_utc.strftime("%Y-%m-%d %H:%M UTC")
                logger.info("[fallback] Запланировано напоминание id=%s chat=%s user=%s due_at=%s silent=%s text=%r",
                            reminder_id, chat_id, user_id, human_time, silent, reminder_text)
                ack = f"✅ Напоминание запланировано на {human_time}: {reminder_text}"
                return visible_text, ack
            except Exception as e:
                logger.warning(f"Не удалось создать напоминание через fallback: {e}")
                return visible_text, None
        # Удаляем все блоки из видимого текста
        visible_text = ChatManager.REMINDER_FENCE_RE.sub("", text).strip()
        # Берём последний блок
        last = matches[-1]
        raw_json = last.group(1).strip()
        try:
            data = json.loads(raw_json)
            when = str(data.get("when", "")).strip()
            reminder_text = str(data.get("text", "")).strip()
            if not when or not reminder_text:
                return visible_text, None
            if len(reminder_text) > 200:
                reminder_text = reminder_text[:200]
            silent = bool(data.get("silent", False))
            due_at_utc = ChatManager._parse_when_to_utc(when)
            if not due_at_utc:
                return visible_text, None
            # Вставляем напоминание
            async with get_conn() as db:
                cur = await db.execute(
                    "INSERT INTO reminders(chat_id, user_id, text, due_at, silent, status) VALUES (?, ?, ?, ?, ?, 'scheduled')",
                    (chat_id, user_id, reminder_text, due_at_utc.strftime("%Y-%m-%d %H:%M:%S"), int(silent)),
                )
                await db.commit()
                reminder_id = getattr(cur, 'lastrowid', None)
            human_time = due_at_utc.strftime("%Y-%m-%d %H:%M UTC")
            logger.info("Запланировано напоминание id=%s chat=%s user=%s due_at=%s silent=%s text=%r",
                        reminder_id, chat_id, user_id, human_time, silent, reminder_text)
            ack = f"✅ Напоминание запланировано на {human_time}: {reminder_text}"
            return visible_text, ack
        except Exception as e:
            logger.warning(f"Не удалось распарсить reminder-блок: {e}")
            return visible_text, None

    @staticmethod
    def _try_parse_ru_reminder_from_text(text: str):
        """Грубый fallback: пытается вытащить reminder из обычного русского текста ответа.
        Ищет паттерны типа: "напоминание <текст> через 3 мин/2 часа 30 минут" или "напомнить <текст> через X".
        Возвращает (reminder_text, due_at_utc, silent) или None.
        """
        # Находим длительность после слова «через»
        m_dur = re.search(r"через\s+([0-9\s]+(?:с|сек|секунд\w*|м|мин|минут\w*|ч|час\w*|д|дн\w*)(?:\s+[0-9]+\s*(?:с|сек|секунд\w*|м|мин|минут\w*|ч|час\w*|д|дн\w*))*)",
                           text, re.IGNORECASE)
        if not m_dur:
            return None
        dur_str = m_dur.group(1).lower()
        # Пытаемся извлечь "текст" до «через»
        rem_text = None
        m_txt = re.search(r"напоминани[ея]\s+(.+?)\s+через\s+", text, re.IGNORECASE)
        if m_txt:
            rem_text = m_txt.group(1).strip().strip('.!?,;:')
        else:
            m_txt2 = re.search(r"напомнить\s+(.+?)\s+через\s+", text, re.IGNORECASE)
            if m_txt2:
                rem_text = m_txt2.group(1).strip().strip('.!?,;:')
        if not rem_text:
            return None
        # Конвертируем длительность в секунды (поддерживает композиции: «2 часа 30 минут»)
        total_seconds = 0
        for amt, unit in re.findall(r"(\d+)\s*(с|сек|секунд\w*|м|мин|минут\w*|ч|час\w*|д|дн\w*)", dur_str):
            v = int(amt)
            if unit.startswith('с'):
                total_seconds += v
            elif unit.startswith('м'):
                total_seconds += v * 60
            elif unit.startswith('ч'):
                total_seconds += v * 3600
            elif unit.startswith('д'):
                total_seconds += v * 86400
        if total_seconds <= 0:
            return None
        due_at_utc = datetime.now(timezone.utc) + timedelta(seconds=total_seconds)
        return rem_text, due_at_utc, False

    @staticmethod
    def _parse_when_to_utc(when_str: str) -> datetime | None:
        """Парсит ISO8601 или строку 'in X' в UTC datetime.
        Поддерживает: 2025-08-13T22:30:00+03:00, 2025-08-13T19:30:00Z, а также 'in 5m', 'in 2h 30m', 'in 1d'.
        """
        try:
            if not when_str:
                return None
            s = when_str.strip()
            # ISO8601 (простая эвристика: начинается с цифры или знака таймзоны)
            if s and (s[0].isdigit() or s.startswith("+") or s.startswith("-")):
                try:
                    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                except Exception:
                    return None
                if dt.tzinfo is None:
                    # Если TZ не указан — считаем это уже UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            # Формат "in X"
            if s.lower().startswith("in "):
                total_seconds = 0
                for amount, unit in re.findall(r"(\d+)\s*([smhd])", s.lower()):
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
                return datetime.now(timezone.utc) + timedelta(seconds=total_seconds)
        except Exception:
            return None
        return None