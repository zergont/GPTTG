"""Чат с использованием OpenAI Responses API."""
from typing import Any, Dict, List
import openai

from bot.config import settings
from bot.utils.db import get_conn
from bot.utils.log import logger
from .base import client, oai_limiter
from .models import ModelsManager


class ChatManager:
    """Управление чатом через OpenAI Responses API."""
    
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

            input_content = []
            if previous_response_id is None:
                input_content.append({
                    "type": "message",
                    "content": settings.system_prompt,
                    "role": "system"
                })
                logger.info(f"Добавлен системный промпт для первого запроса в чате {chat_id}")
            else:
                logger.info(f"Используется previous_response_id={previous_response_id}, системный промпт пропущен")

            input_content.extend(user_content)

            request_params = {
                "model": current_model,
                "input": input_content,
                "previous_response_id": previous_response_id,
                "store": True,
            }

            # Инструменты
            use_web = True if enable_web_search is None else bool(enable_web_search)
            if use_web:
                request_params.setdefault("tools", []).append({"type": "web_search"})
            if tools:
                request_params.setdefault("tools", []).extend(tools)
            if tool_choice:
                request_params["tool_choice"] = tool_choice

            # DEBUG-запрос
            if getattr(settings, "debug_mode", False):
                logger.debug(f"[DEBUG] OpenAI REQUEST: {request_params}")

            try:
                response = await client.responses.create(**request_params)
            except openai.APITimeoutError:
                logger.error("OpenAI: превышено время ожидания ответа")
                return "⏳ Превышено время ожидания ответа. Попробуйте еще раз."
            except openai.RateLimitError as e:
                logger.error("OpenAI: превышен лимит запросов")
                error_details = str(e)
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

            # Извлечение текста
            if getattr(response, "output", None):
                try:
                    for message in response.output:
                        if hasattr(message, 'content') and message.content:
                            for content_item in message.content:
                                if hasattr(content_item, 'text') and content_item.text:
                                    return content_item.text
                                elif getattr(content_item, 'type', '') == 'output_text' and hasattr(content_item, 'text'):
                                    return content_item.text
                except Exception as e:
                    logger.error(f"Ошибка при обработке ответа: {e}")

            logger.warning("Не удалось извлечь текст из ответа OpenAI")
            return "Извините, не удалось обработать ответ. Попробуйте еще раз."