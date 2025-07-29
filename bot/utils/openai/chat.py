"""Чат с использованием OpenAI Responses API."""
import asyncio
from typing import Any, Dict, List
import backoff
from aiohttp import ClientError
from openai import OpenAIError
import openai

from bot.config import settings
from bot.utils.db import get_conn
from bot.utils.log import logger
from .base import client, RATE_LIMIT
from .models import ModelsManager
from .files import FilesManager


class ChatManager:
    """Управление чатом через OpenAI Responses API."""
    
    @staticmethod
    @backoff.on_exception(
        backoff.expo, 
        (OpenAIError, ClientError), 
        max_tries=3, 
        jitter=backoff.random_jitter,
        max_time=60
    )
    async def responses_request(
        chat_id: int,
        user_content: List[Dict[str, Any]],
        previous_response_id: str | None = None,
    ) -> str:
        """Вызов Responses API + учёт расхода токенов."""
        async with RATE_LIMIT:
            logger.info("Запрос в OpenAI (chat=%s, prev=%s)", 
                       chat_id, previous_response_id)
            
            # Используем текущую модель (все доступные модели поддерживают vision+Responses API)
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
                "store": True
            }

            # DEBUG: выводим запрос
            if getattr(settings, "debug_mode", False):
                logger.info(f"[DEBUG] OpenAI REQUEST: {request_params}")

            try:
                response = await client.responses.create(**request_params)
            except openai.APITimeoutError:
                logger.error("OpenAI: превышено время ожидания ответа")
                raise
            except openai.RateLimitError:
                logger.error("OpenAI: превышен лимит запросов")
                await asyncio.sleep(1)
                raise
            except (openai.PermissionDeniedError, openai.BadRequestError) as e:
                error_message = str(e)
                logger.warning(f"Проблема с моделью {current_model}: {error_message}")
                
                # Возвращаемся к безопасной модели и НЕ повторяем запрос
                # Просто возвращаем ошибку пользователю
                await ModelsManager.set_current_model("gpt-4o-mini")
                
                # Формируем понятное сообщение для пользователя
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
                raise

            # DEBUG: выводим ответ
            if getattr(settings, "debug_mode", False):
                logger.info(f"[DEBUG] OpenAI RESPONSE: {response}")

            usage = response.usage.total_tokens
            cost = usage / 1000 * settings.openai_price_per_1k_tokens

            async with get_conn() as db:
                await db.execute(
                    "REPLACE INTO chat_history(chat_id, last_response) VALUES (?, ?)",
                    (chat_id, response.id),
                )
                await db.execute(
                    "INSERT INTO usage(chat_id, user_id, tokens, cost, model) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, chat_id, usage, cost, response.model),
                )
                await db.commit()

            # Улучшенная обработка ответа
            if response.output:
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