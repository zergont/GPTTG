"""Чат с использованием OpenAI Responses API."""
from typing import Any, Dict, List, Tuple
import re
import json
from datetime import datetime, timezone, timedelta
import openai

from bot.config import settings
from bot.utils.db import get_conn
from bot.utils.log import logger
from .base import client, oai_limiter
from .models import ModelsManager
from bot.utils.http_client import get_session


class ChatManager:
    """Управление чатом через OpenAI Responses API."""

    @staticmethod
    def _extract_args_dict(args_obj: Any) -> Dict[str, Any]:
        """Преобразует аргументы tool-call к dict (поддержка str(JSON), pydantic, __dict__)."""
        try:
            if args_obj is None:
                return {}
            if isinstance(args_obj, dict):
                return args_obj
            if isinstance(args_obj, str):
                try:
                    return json.loads(args_obj)
                except Exception:
                    return {}
            if hasattr(args_obj, "model_dump"):
                return args_obj.model_dump()
            if hasattr(args_obj, "__dict__"):
                return dict(args_obj.__dict__)
        except Exception:
            pass
        return {}

    @staticmethod
    async def _handle_schedule_reminder_tool(chat_id: int, user_id: int, args: Dict[str, Any]) -> Tuple[str | None, Dict[str, Any] | None]:
        """Обрабатывает tool-call schedule_reminder: валидирует, создаёт запись и возвращает (ACK, tool_output_payload)."""
        when = str(args.get("when", "")).strip()
        text_val = str(args.get("text", "")).strip()
        silent = bool(args.get("silent", False))
        if not when or not text_val:
            return None, None
        due_at_utc = ChatManager._parse_when_to_utc(when)
        if not due_at_utc:
            return None, None
        try:
            async with get_conn() as db:
                cur = await db.execute(
                    "INSERT INTO reminders(chat_id, user_id, text, due_at, silent, status) VALUES (?, ?, ?, ?, ?, 'scheduled')",
                    (chat_id, user_id, text_val[:200], due_at_utc.strftime("%Y-%m-%d %H:%M:%S"), int(silent)),
                )
                await db.commit()
                reminder_id = getattr(cur, 'lastrowid', None)
            human_time = due_at_utc.strftime("%Y-%m-%d %H:%M UTC")
            logger.info("[tool] Запланировано напоминание id=%s chat=%s user=%s due_at=%s silent=%s text=%r",
                        reminder_id, chat_id, user_id, human_time, silent, text_val)
            ack = f"✅ Напоминание запланировано на {human_time}: {text_val}"
            tool_output = {
                "ok": True,
                "reminder_id": reminder_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "when_utc": human_time,
                "silent": silent,
                "text": text_val,
            }
            return ack, tool_output
        except Exception as e:
            logger.warning(f"Не удалось создать напоминание из tool-call: {e}")
            return None, {"ok": False, "error": str(e)}

    @staticmethod
    def _has_reminder_intent(user_content: List[Dict[str, Any]]) -> bool:
        """Грубая эвристика: определяет, просит ли пользователь поставить напоминание."""
        try:
            text_parts: List[str] = []
            for m in user_content:
                if isinstance(m, dict) and m.get("role") == "user":
                    c = m.get("content")
                    if isinstance(c, str):
                        text_parts.append(c.lower())
            if not text_parts:
                return False
            text = "\n".join(text_parts)
            return (
                ("напомн" in text) or ("напоминан" in text) or ("remind" in text) or ("reminder" in text)
            )
        except Exception:
            return False

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
        Единственный способ планирования напоминаний — function-tool schedule_reminder({when,text,silent}).
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

            # Инструкция по напоминаниям: только function-tool, без скрытых блоков
            reminder_instr = (
                "\n\nНапоминания: используй только function-tool 'schedule_reminder' с полями "
                "when (ISO8601 с TZ или 'in 5m/2h/1d'), text (до 200 символов, без префикса 'Напоминание:'), "
                "silent (true/false). Не вставляй скрытые блоки ```reminder``` в видимый ответ."
            )

            if previous_response_id is None:
                input_content.append({
                    "type": "message",
                    "content": settings.system_prompt + reminder_instr,
                    "role": "system",
                })
                logger.info(f"Добавлен системный промпт для первого запроса в чате {chat_id}")
            else:
                input_content.append({
                    "type": "message",
                    "content": (
                        "Для напоминаний вызывай только function-tool schedule_reminder({when,text,silent}). "
                        "Не добавляй скрытые блоки."
                    ),
                    "role": "system",
                })
                logger.info(f"Используется previous_response_id={previous_response_id}, системный промпт сокращён")

            # Добавляем пользовательский ввод
            input_content.extend(user_content)

            # Авто-режим для напоминаний: принудить вызов функции
            is_reminder_intent = ChatManager._has_reminder_intent(user_content)

            request_params: Dict[str, Any] = {
                "model": current_model,
                "input": input_content,
                "previous_response_id": previous_response_id,
                "store": True,
            }

            # Инструменты
            tools_list = []
            use_web = True if enable_web_search is None else bool(enable_web_search)
            # Не отключаем веб-поиск даже при интенте напоминаний — модель может нуждаться в актуальных данных
            if use_web:
                tools_list.append({"type": "web_search"})
            tools_list.append({
                "type": "function",
                "name": "schedule_reminder",
                "description": "Schedule a one-time reminder for the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "when": {"type": "string", "description": "When to trigger: ISO8601 with timezone or relative 'in 5m/2h/1d'"},
                        "text": {"type": "string", "description": "Short reminder text, up to 200 chars"},
                        "silent": {"type": "boolean", "description": "Send without notification sound", "default": False}
                    },
                    "required": ["when", "text"],
                    "additionalProperties": False
                }
            })
            if tools:
                tools_list.extend(tools)
            if tools_list:
                request_params["tools"] = tools_list

            if tool_choice:
                request_params["tool_choice"] = tool_choice
            elif is_reminder_intent:
                request_params["tool_choice"] = "required"

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
                cached_t = max(0, int(cached_input_tokens)) if cached_input_tokens is not None else 0
                regular_t = max(0, int(input_tokens) - cached_t)
                cost = (regular_t / 1000.0) * in_price + (cached_t / 1000.0) * cached_price + (int(output_tokens) / 1000.0) * out_price
            else:
                cost = total_tokens / 1000.0 * settings.openai_price_per_1k_tokens

            # Обрабатываем вызовы function-tools (schedule_reminder)
            tool_acks: List[str] = []
            tool_outputs_submit: List[Dict[str, str]] = []
            if getattr(response, "output", None):
                for item in response.output:
                    try:
                        # Отдельный function_call
                        name = getattr(item, "name", None)
                        args_obj = getattr(item, "arguments", None) or getattr(item, "parameters", None) or getattr(item, "args", None)
                        call_id = getattr(item, "call_id", None) or getattr(item, "id", None)
                        if name == "schedule_reminder":
                            args = ChatManager._extract_args_dict(args_obj)
                            ack, tool_out = await ChatManager._handle_schedule_reminder_tool(chat_id, user_id, args)
                            if ack:
                                tool_acks.append(ack)
                            if call_id and tool_out is not None:
                                tool_outputs_submit.append({
                                    "tool_call_id": call_id,
                                    "output": json.dumps(tool_out, ensure_ascii=False)
                                })
                        # Вложенный tool_call
                        if hasattr(item, 'content') and item.content:
                            for content_item in item.content:
                                ctype = getattr(content_item, 'type', '') or ''
                                if ctype in ("tool_call", "tool_use", "function_call"):
                                    name2 = getattr(content_item, 'name', None)
                                    args2 = (getattr(content_item, 'arguments', None)
                                             or getattr(content_item, 'input', None)
                                             or getattr(content_item, 'parameters', None)
                                             or getattr(content_item, 'args', None))
                                    call_id2 = getattr(content_item, 'call_id', None) or getattr(content_item, 'id', None)
                                    if name2 == "schedule_reminder":
                                        args = ChatManager._extract_args_dict(args2)
                                        ack, tool_out = await ChatManager._handle_schedule_reminder_tool(chat_id, user_id, args)
                                        if ack:
                                            tool_acks.append(ack)
                                        if call_id2 and tool_out is not None:
                                            tool_outputs_submit.append({
                                                "tool_call_id": call_id2,
                                                "output": json.dumps(tool_out, ensure_ascii=False)
                                            })
                    except Exception as e:
                        logger.debug(f"Игнорируем элемент output при разборе tool-calls: {e}")

            submitted_ok = False
            if tool_outputs_submit:
                try:
                    submit_method = getattr(getattr(client, 'responses', None), 'submit_tool_outputs', None)
                    if submit_method is not None:
                        await submit_method(response_id=response.id, tool_outputs=tool_outputs_submit)
                        submitted_ok = True
                    else:
                        # Фоллбек через REST
                        session = get_session()
                        url = f"https://api.openai.com/v1/responses/{response.id}/tool_outputs"
                        headers = {
                            "Authorization": f"Bearer {settings.openai_api_key}",
                            "Content-Type": "application/json",
                        }
                        payload = {"tool_outputs": tool_outputs_submit}
                        async with session.post(url, headers=headers, json=payload) as resp:
                            if 200 <= resp.status < 300:
                                submitted_ok = True
                            else:
                                body = await resp.text()
                                raise RuntimeError(f"HTTP {resp.status}: {body[:200]}")
                except Exception as e:
                    logger.debug(f"submit_tool_outputs failed/ignored: {e}")

            # Извлекаем текст без каких-либо проверок скрытых блоков
            full_text = ""
            if getattr(response, "output", None):
                try:
                    parts: List[str] = []
                    for message in response.output:
                        if hasattr(message, 'content') and message.content:
                            for content_item in message.content:
                                if getattr(content_item, 'type', '') == 'output_text' and hasattr(content_item, 'text') and content_item.text:
                                    parts.append(content_item.text)
                                elif hasattr(content_item, 'text') and content_item.text:
                                    parts.append(content_item.text)
                    full_text = "\n".join(parts).strip()
                except Exception as e:
                    logger.error(f"Ошибка при сборке текста ответа: {e}")
            visible_text = (full_text or "").strip()

            # Сохраняем метрики и last_response
            async with get_conn() as db:
                last_resp_to_store = response.id
                if tool_outputs_submit and not submitted_ok:
                    last_resp_to_store = None
                await db.execute(
                    "REPLACE INTO chat_history(chat_id, last_response) VALUES (?, ?)",
                    (chat_id, last_resp_to_store),
                )
                await db.execute(
                    "INSERT INTO usage(chat_id, user_id, tokens, cost, model) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, user_id, total_tokens, cost, getattr(response, "model", current_model)),
                )
                await db.commit()

            if tool_acks:
                if visible_text:
                    return f"{visible_text}\n\n" + "\n".join(tool_acks)
                return "\n".join(tool_acks)
            return visible_text

    @staticmethod
    def _parse_when_to_utc(when_str: str) -> datetime | None:
        """Парсит ISO8601 или строку 'in X' в UTC datetime.
        Поддерживает: 2025-08-13T22:30:00+03:00, 2025-08-13T19:30:00Z, а также 'in 5m', 'in 2h 30m', 'in 1d'.
        """
        try:
            if not when_str:
                return None
            s = when_str.strip()
            if s and (s[0].isdigit() or s.startswith("+") or s.startswith("-")):
                try:
                    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                except Exception:
                    return None
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
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