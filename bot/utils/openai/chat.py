"""Чат с использованием OpenAI Responses API."""
from typing import Any, Dict, List, Tuple
import re
import json
import asyncio
from datetime import datetime, timezone, timedelta
import openai

from bot.config import settings
from bot.utils.db import get_conn, get_user_timezone, set_user_timezone
from bot.utils.log import logger
from .base import client, oai_limiter
from .models import ModelsManager
from bot.utils.http_client import get_session  # may still be used elsewhere
from bot.utils.datetime_context import utc_to_user_local


class ChatManager:
    """Управление чатом через OpenAI Responses API."""

    @staticmethod
    def _extract_args_dict(args_obj: Any) -> Dict[str, Any]:
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
            human_time_utc = due_at_utc.strftime("%Y-%m-%d %H:%M:%S")
            user_tz = await get_user_timezone(user_id)
            human_time_local = utc_to_user_local(human_time_utc, user_tz)
            logger.info("[tool] Запланировано напоминание id=%s chat=%s user=%s due_at=%s silent=%s text=%r",
                        reminder_id, chat_id, user_id, human_time_utc, silent, text_val)
            ack = f"✅ Напоминание запланировано на {human_time_local} ({user_tz}): {text_val}"
            tool_output = {
                "ok": True,
                "reminder_id": reminder_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "when_utc": human_time_utc,
                "silent": silent,
                "text": text_val,
            }
            return ack, tool_output
        except Exception as e:
            logger.warning(f"Не удалось создать напоминание из tool-call: {e}")
            return None, {"ok": False, "error": str(e)}

    @staticmethod
    async def _handle_schedule_reminders_tool(chat_id: int, user_id: int, args: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any] | None]:
        items = args.get("items")
        if not isinstance(items, list) or not items:
            return [], None
        acks: List[str] = []
        created: List[Dict[str, Any]] = []
        user_tz = await get_user_timezone(user_id)
        for it in items:
            try:
                if not isinstance(it, dict):
                    continue
                when = str(it.get("when", "")).strip()
                text_val = str(it.get("text", "")).strip()
                silent = bool(it.get("silent", False))
                if not when or not text_val:
                    continue
                due_at_utc = ChatManager._parse_when_to_utc(when)
                if not due_at_utc:
                    continue
                async with get_conn() as db:
                    cur = await db.execute(
                        "INSERT INTO reminders(chat_id, user_id, text, due_at, silent, status) VALUES (?, ?, ?, ?, ?, 'scheduled')",
                        (chat_id, user_id, text_val[:200], due_at_utc.strftime("%Y-%m-%d %H:%M:%S"), int(silent)),
                    )
                    await db.commit()
                    reminder_id = getattr(cur, 'lastrowid', None)
                human_time_utc = due_at_utc.strftime("%Y-%m-%d %H:%M:%S")
                human_time_local = utc_to_user_local(human_time_utc, user_tz)
                logger.info("[tool] Запланировано напоминание id=%s chat=%s user=%s due_at=%s silent=%s text=%r",
                            reminder_id, chat_id, user_id, human_time_utc, silent, text_val)
                acks.append(f"✅ Напоминание запланировано на {human_time_local} ({user_tz}): {text_val}")
                created.append({
                    "reminder_id": reminder_id,
                    "when_utc": human_time_utc,
                    "silent": silent,
                    "text": text_val,
                })
            except Exception as e:
                logger.warning(f"Не удалось создать одно из пакетных напоминаний: {e}")
                continue
        if not created:
            return [], {"ok": False, "error": "no_valid_items"}
        return acks, {"ok": True, "created": created, "count": len(created)}

    @staticmethod
    def _has_reminder_intent(user_content: List[Dict[str, Any]]) -> bool:
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
    def _iter_output_items(resp_like: Any):
        if resp_like is None:
            return []
        try:
            if hasattr(resp_like, 'output') and resp_like.output:
                return list(resp_like.output)
            if isinstance(resp_like, dict) and resp_like.get('output'):
                return list(resp_like['output'])
        except Exception:
            pass
        return []

    @staticmethod
    def _extract_text_from_output(resp_like: Any) -> str:
        parts: List[str] = []
        for message in ChatManager._iter_output_items(resp_like):
            try:
                content = getattr(message, 'content', None)
                if content is None and isinstance(message, dict):
                    content = message.get('content')
                if not content:
                    continue
                for ci in content:
                    ctype = getattr(ci, 'type', None) if not isinstance(ci, dict) else ci.get('type')
                    text = getattr(ci, 'text', None) if not isinstance(ci, dict) else ci.get('text')
                    if ctype == 'output_text' and text:
                        parts.append(text)
                    elif text:
                        parts.append(text)
            except Exception:
                continue
        return "\n".join([p for p in parts if p]).strip()

    @staticmethod
    async def _handle_set_timezone_tool(user_id: int, args: Dict[str, Any]) -> Dict[str, Any]:
        tz = str(args.get("timezone", "")).strip()
        if not tz:
            return {"ok": False, "error": "empty"}
        ok = await set_user_timezone(user_id, tz)
        return {"ok": ok, "timezone": tz}

    @staticmethod
    async def _collect_tool_calls(chat_id: int, user_id: int, resp_like: Any) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Возвращает (acks, function_call_output[]) для всех tool-calls (schedule_reminder/schedule_reminders)."""
        acks: List[str] = []
        fc_outputs: List[Dict[str, Any]] = []
        for item in ChatManager._iter_output_items(resp_like):
            try:
                # Основной уровень
                name = getattr(item, 'name', None) if not isinstance(item, dict) else item.get('name')
                args_obj = (
                    getattr(item, 'arguments', None) if not isinstance(item, dict) else item.get('arguments')
                ) or (
                    getattr(item, 'parameters', None) if not isinstance(item, dict) else item.get('parameters')
                ) or (
                    getattr(item, 'args', None) if not isinstance(item, dict) else item.get('args')
                )
                call_id = (
                    getattr(item, 'call_id', None) if not isinstance(item, dict) else item.get('call_id')
                ) or (
                    getattr(item, 'id', None) if not isinstance(item, dict) else item.get('id')
                )
                if name == "schedule_reminder":
                    args = ChatManager._extract_args_dict(args_obj)
                    ack, tool_out = await ChatManager._handle_schedule_reminder_tool(chat_id, user_id, args)
                    if ack:
                        acks.append(ack)
                    if call_id and tool_out is not None:
                        fc_outputs.append({
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(tool_out, ensure_ascii=False)
                        })
                elif name == "schedule_reminders":
                    args = ChatManager._extract_args_dict(args_obj)
                    acks_list, tool_out = await ChatManager._handle_schedule_reminders_tool(chat_id, user_id, args)
                    if acks_list:
                        acks.extend(acks_list)
                    if call_id and tool_out is not None:
                        fc_outputs.append({
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(tool_out, ensure_ascii=False)
                        })
                elif name == "set_timezone":
                    args = ChatManager._extract_args_dict(args_obj)
                    tool_out = await ChatManager._handle_set_timezone_tool(user_id, args)
                    if tool_out.get("ok"):
                        acks.append(f"🕒 Часовой пояс обновлён: {tool_out.get('timezone')}")
                    if call_id:
                        fc_outputs.append({
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(tool_out, ensure_ascii=False)
                        })
                # Вложенные tool_call'ы
                content = getattr(item, 'content', None) if not isinstance(item, dict) else item.get('content')
                if content:
                    for content_item in content:
                        ctype = getattr(content_item, 'type', '') if not isinstance(content_item, dict) else content_item.get('type') or ''
                        if ctype in ("tool_call", "tool_use", "function_call"):
                            name2 = getattr(content_item, 'name', None) if not isinstance(content_item, dict) else content_item.get('name')
                            args2 = (
                                getattr(content_item, 'arguments', None) if not isinstance(content_item, dict) else content_item.get('arguments')
                            ) or (
                                getattr(content_item, 'input', None) if not isinstance(content_item, dict) else content_item.get('input')
                            ) or (
                                getattr(content_item, 'parameters', None) if not isinstance(content_item, dict) else content_item.get('parameters')
                            ) or (
                                getattr(content_item, 'args', None) if not isinstance(content_item, dict) else content_item.get('args')
                            )
                            call_id2 = (
                                getattr(content_item, 'call_id', None) if not isinstance(content_item, dict) else content_item.get('call_id')
                            ) or (
                                getattr(content_item, 'id', None) if not isinstance(content_item, dict) else content_item.get('id')
                            )
                            if name2 == "schedule_reminder":
                                args = ChatManager._extract_args_dict(args2)
                                ack, tool_out = await ChatManager._handle_schedule_reminder_tool(chat_id, user_id, args)
                                if ack:
                                    acks.append(ack)
                                if call_id2 and tool_out is not None:
                                    fc_outputs.append({
                                        "type": "function_call_output",
                                        "call_id": call_id2,
                                        "output": json.dumps(tool_out, ensure_ascii=False)
                                    })
                            elif name2 == "schedule_reminders":
                                args = ChatManager._extract_args_dict(args2)
                                acks_list, tool_out = await ChatManager._handle_schedule_reminders_tool(chat_id, user_id, args)
                                if acks_list:
                                    acks.extend(acks_list)
                                if call_id2 and tool_out is not None:
                                    fc_outputs.append({
                                        "type": "function_call_output",
                                        "call_id": call_id2,
                                        "output": json.dumps(tool_out, ensure_ascii=False)
                                    })
            except Exception:
                continue
        return acks, fc_outputs

    @staticmethod
    async def responses_request(
        chat_id: int,
        user_id: int,
        user_content: List[Dict[str, Any]],
        previous_response_id: str | None = None,
        tools: list | None = None,
        enable_web_search: bool | None = None,
        tool_choice: str | None = None,
        include_reminder_tools: bool = True
    ) -> str:
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

            tz_intro = (
                "По умолчанию предполагай часовой пояс пользователя Europe/Moscow. "
                "Если видишь в диалоге явные признаки другого пояса (город, текущее время, GMT±X) — уточни и установи через tool set_timezone. "
                "Спрашивай про город или текущее время только один раз при первом общении, не злоупотребляй напоминаниями."
            )

            if include_reminder_tools:
                reminder_instr = (
                    "\n\nНапоминания: используй function-tool 'schedule_reminder' с полями "
                    "when (ISO8601 с TZ или 'in 5m/2h/1d'), text (до 200 символов), silent (true/false). "
                    "Выбор инструментов — автоматический (tool_choice=auto): модель сама решает, когда вызывать функцию, а когда ответить текстом. "
                    "Если пользователь просит несколько напоминаний, вызови schedule_reminder несколько раз в одном ответе первого шага (пакетом). "
                    "Также доступен пакетный инструмент 'schedule_reminders' с массивом items[{when,text,silent?}], его можно использовать для нескольких напоминаний сразу. "
                    "Создавай разумное количество напоминаний и не спамь пользователя; при неопределённости уточни детали. "
                    "Не отправляй отдельные сообщения-подтверждения — бот покажет итоговые подтверждения самостоятельно."
                )
            else:
                reminder_instr = (
                    "\n\nЭто уведомление по уже установленному напоминанию. "
                    "Сформируй одно короткое понятное уведомление для пользователя без лишних вступлений. "
                    "Не предлагай ставить новые напоминания и не вызывай инструментов напоминаний."
                )

            sys_text = f"{settings.system_prompt}\n\n{tz_intro}{reminder_instr}"

            if previous_response_id is None:
                input_content.append({"type": "message", "content": sys_text, "role": "system"})
            else:
                input_content.append({
                    "type": "message",
                    "content": tz_intro + (" Для напоминаний используй schedule_reminder/schedule_reminders." if include_reminder_tools else ""),
                    "role": "system",
                })

            input_content.extend(user_content)

            request_params: Dict[str, Any] = {
                "model": current_model,
                "input": input_content,
                "previous_response_id": previous_response_id,
                "store": True,
                "max_tool_calls": 8,
            }

            tools_list = []
            use_web = True if enable_web_search is None else bool(enable_web_search)
            if use_web:
                tools_list.append({"type": "web_search"})

            # set_timezone tool всегда доступен
            tools_list.append({
                "type": "function",
                "name": "set_timezone",
                "description": "Set user's IANA timezone, e.g., 'Europe/Moscow'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string", "description": "IANA timezone name"}
                    },
                    "required": ["timezone"],
                    "additionalProperties": False
                }
            })

            if include_reminder_tools:
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
                tools_list.append({
                    "type": "function",
                    "name": "schedule_reminders",
                    "description": "Schedule multiple one-time reminders in a single call.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "when": {"type": "string"},
                                        "text": {"type": "string"},
                                        "silent": {"type": "boolean", "default": False}
                                    },
                                    "required": ["when", "text"],
                                    "additionalProperties": False
                                },
                                "minItems": 1
                            }
                        },
                        "required": ["items"],
                        "additionalProperties": False
                    }
                })

            if tools:
                tools_list.extend(tools)
            if tools_list:
                request_params["tools"] = tools_list

            if tool_choice:
                request_params["tool_choice"] = tool_choice

            if getattr(settings, "debug_mode", False):
                logger.debug(f"[DEBUG] OpenAI REQUEST: {request_params}")

            # Выполняем запрос с лечением кейса незакрытых tool-calls без сброса истории
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
            except openai.BadRequestError as e:
                error_message = str(e)
                # Лечим кейс: "No tool output found for function call call_..."
                if previous_response_id and ("No tool output found for function call" in error_message or "tool output" in error_message):
                    call_id_match = re.search(r"function call\s+(call_[A-Za-z0-9]+)", error_message)
                    missing_call_id = call_id_match.group(1) if call_id_match else None
                    if missing_call_id:
                        logger.warning(f"Незакрытый tool-call {missing_call_id}. Отправляю фиктивный function_call_output и повторяю запрос.")
                        try:
                            close_resp = await asyncio.wait_for(
                                client.responses.create(
                                    model=current_model,
                                    previous_response_id=previous_response_id,
                                    input=[{
                                        "type": "function_call_output",
                                        "call_id": missing_call_id,
                                        "output": json.dumps({"ok": False, "error": "aborted_by_system"}, ensure_ascii=False)
                                    }],
                                    store=True,
                                ),
                                timeout=12,
                            )
                            new_prev = getattr(close_resp, 'id', previous_response_id)
                            request_params_retry = dict(request_params)
                            request_params_retry["previous_response_id"] = new_prev
                            response = await asyncio.wait_for(
                                client.responses.create(**request_params_retry),
                                timeout=20,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Таймаут при закрытии зависшего tool-call/повторе запроса")
                            return (
                                "⚠️ Таймаут при закрытии зависшего вызова инструмента. "
                                "Повторите запрос ещё раз."
                            )
                        except Exception as e2:
                            logger.warning(f"Не удалось закрыть tool-call {missing_call_id}: {e2}")
                            return (
                                "⚠️ Предыдущий шаг ожидал вывод инструмента, из-за чего запрос не выполнен. "
                                "Повторите запрос ещё раз."
                            )
                    else:
                        logger.warning("Не удалось извлечь call_id из сообщения ошибки tool output")
                        return (
                            "⚠️ Контекст ожидает завершения вызова инструмента. Повторите запрос ещё раз."
                        )
                else:
                    # Прочие 400: покажем расшифровку без смены модели
                    logger.warning(f"Проблема с моделью {current_model}: {error_message}")
                    if "does not have access" in error_message:
                        return (
                            f"❌ Нет доступа к модели <code>{current_model}</code>.\n"
                            f"Попросите доступ у админа или выберите другую модель через /setmodel."
                        )
                    elif "not supported with the Responses API" in error_message:
                        return (
                            f"❌ Модель <code>{current_model}</code> не поддерживает Responses API.\n"
                            f"Выберите совместимую модель через /setmodel."
                        )
                    elif "does not support image inputs" in error_message:
                        return (
                            f"❌ Модель <code>{current_model}</code> не поддерживает изображения.\n"
                            f"Отправьте текстовый запрос или смените модель через /setmodel."
                        )
                    else:
                        short = error_message[:200]
                        return f"❌ Проблема с моделью <code>{current_model}</code>: {short}"
            except openai.PermissionDeniedError as e:
                error_message = str(e)
                logger.warning(f"Проблема с моделью {current_model}: {error_message}")
                if "does not have access" in error_message:
                    return (
                        f"❌ Нет доступа к модели <code>{current_model}</code>.\n"
                        f"Попросите доступ у админа или выберите другую модель через /setmodel."
                    )
                else:
                    short = error_message[:200]
                    return f"❌ Проблема с моделью <code>{current_model}</code>: {short}"
            except Exception as e:
                logger.error(f"OpenAI:unexpected error: {e}")
                return f"❌ ПроизошлаUnexpected ошибка: {str(e)[:100]}..."

            # Первый шаг — usage/cost
            usage1 = getattr(response, "usage", None)
            total_tokens1 = getattr(usage1, "total_tokens", 0) if usage1 else 0
            prices = ModelsManager.get_model_prices(getattr(response, "model", None) or current_model)
            in_price = prices.get("input", settings.openai_price_per_1k_tokens)
            out_price = prices.get("output", settings.openai_price_per_1k_tokens)
            cached_price = prices.get("cached_input", in_price)
            input_tokens1 = getattr(usage1, "prompt_tokens", None) or getattr(usage1, "input_tokens", None)
            output_tokens1 = getattr(usage1, "completion_tokens", None) or getattr(usage1, "output_tokens", None)
            cached_input_tokens1 = getattr(usage1, "cached_prompt_tokens", None) or getattr(usage1, "cached_input_tokens", None)
            if input_tokens1 is not None and output_tokens1 is not None:
                cached_t1 = max(0, int(cached_input_tokens1)) if cached_input_tokens1 is not None else 0
                regular_t1 = max(0, int(input_tokens1) - cached_t1)
                cost1 = (regular_t1 / 1000.0) * in_price + (cached_t1 / 1000.0) * cached_price + (int(output_tokens1) / 1000.0) * out_price
            else:
                cost1 = total_tokens1 / 1000.0 * settings.openai_price_per_1k_tokens

            # Итеративно обрабатываем tool-calls и продолжаем до 3 шагов
            max_loops = 3
            loop_count = 0
            visible_parts: List[str] = []
            acks_total: List[str] = []
            last_resp_id = getattr(response, 'id', None)

            # Текст ассистента из первого шага, если был
            text1 = ChatManager._extract_text_from_output(response)
            if text1:
                visible_parts.append(text1)

            # Цикл обработки tools
            current_resp = response
            while loop_count < max_loops:
                loop_count += 1
                acks, fc_outputs = await ChatManager._collect_tool_calls(chat_id, user_id, current_resp)
                if acks:
                    acks_total.extend(acks)
                if not fc_outputs:
                    break
                try:
                    cont_resp = await client.responses.create(
                        model=current_model,
                        previous_response_id=last_resp_id,
                        input=fc_outputs,
                        store=True,
                    )
                except Exception as e:
                    logger.debug(f"Второй/последующий шаг (function_call_output) не выполнен: {e}")
                    break
                # Текст из продолжения
                t = ChatManager._extract_text_from_output(cont_resp)
                if t:
                    visible_parts.append(t)
                last_resp_id = getattr(cont_resp, 'id', last_resp_id)
                current_resp = cont_resp

            visible_text = "\n\n".join([p for p in visible_parts if p]).strip()

            # Сохраняем метрики и last_response
            async with get_conn() as db:
                await db.execute(
                    "REPLACE INTO chat_history(chat_id, last_response) VALUES (?, ?)",
                    (chat_id, last_resp_id),
                )
                await db.execute(
                    "INSERT INTO usage(chat_id, user_id, tokens, cost, model) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, user_id, total_tokens1, cost1, getattr(response, "model", current_model)),
                )
                await db.commit()

            # Возвращаем ACK и текст ассистента вместе, если оба есть
            if acks_total and visible_text:
                return "\n".join(acks_total) + "\n\n" + visible_text
            if visible_text:
                return visible_text
            if acks_total:
                return "\n".join(acks_total)
            return ""

    @staticmethod
    def _parse_when_to_utc(when_str: str) -> datetime | None:
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