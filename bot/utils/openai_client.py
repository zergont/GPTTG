"""Асинхронная работа с OpenAI SDK."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Union
import io

import backoff
from aiohttp import ClientError
from openai import AsyncOpenAI, OpenAIError
import openai

from bot.config import settings
from bot.utils.db import get_conn
from bot.utils.log import logger

# Увеличен таймаут для мультимодальных запросов
client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    timeout=60,  # Увеличен с 30 до 60 секунд для работы с файлами
    max_retries=2
)

class OpenAIClient:
    """Основные обращения к OpenAI."""

    RATE_LIMIT = asyncio.Semaphore(4)

    @classmethod
    async def upload_file(cls, file_data: bytes, filename: str, purpose: str = "user_data", chat_id: int | None = None) -> str:
        """Загружает файл в OpenAI, возвращает file_id и сохраняет его в БД если chat_id указан."""
        async with cls.RATE_LIMIT:
            logger.info(f"Загружаем файл {filename} в OpenAI")
            file_obj = io.BytesIO(file_data)
            file_obj.name = filename
            try:
                file_response = await client.files.create(
                    file=file_obj,
                    purpose=purpose
                )
                logger.info(f"Файл загружен с ID: {file_response.id}")
                if chat_id is not None:
                    from bot.utils.db import save_openai_file_id
                    await save_openai_file_id(chat_id, file_response.id)
                if getattr(settings, "debug_mode", False):
                    logger.info(f"[DEBUG] UPLOAD FILE RESPONSE: {file_response}")
                return file_response.id
            except openai.BadRequestError as e:
                logger.error(f"Ошибка формата при загрузке файла: {e}")
                raise
            except openai.AuthenticationError as e:
                logger.error(f"Ошибка аутентификации: {e}")
                raise
            except Exception as e:
                logger.error(f"Непредвиденная ошибка загрузки файла: {e}")
                raise

    @classmethod
    async def delete_files_by_chat(cls, chat_id: int):
        """Удаляет все файлы, загруженные этим чатом в OpenAI, и очищает их из БД."""
        from bot.utils.db import get_openai_file_ids_by_chat, delete_openai_file_ids_by_chat
        file_ids = await get_openai_file_ids_by_chat(chat_id)
        deleted = 0
        for file_id in file_ids:
            try:
                await client.files.delete(file_id)
                deleted += 1
            except Exception as e:
                logger.error(f"Ошибка удаления файла {file_id} из OpenAI: {e}")
        await delete_openai_file_ids_by_chat(chat_id)
        logger.info(f"Удалено {deleted} файлов OpenAI для чата {chat_id}")

    @classmethod
    async def get_current_model(cls) -> str:
        async with get_conn() as db:
            cur = await db.execute(
                "SELECT value FROM bot_settings WHERE key = 'current_model'"
            )
            row = await cur.fetchone()
            return row[0] if row else "gpt-4o-mini"

    @classmethod
    async def set_current_model(cls, model: str) -> None:
        async with get_conn() as db:
            await db.execute(
                "REPLACE INTO bot_settings (key, value) VALUES ('current_model', ?)",
                (model,)
            )
            await db.commit()

    @classmethod
    async def get_available_models(cls) -> List[Dict[str, Any]]:
        try:
            async with cls.RATE_LIMIT:
                models_response = await client.models.list()
                chat_models = []
                for model in models_response.data:
                    model_id = model.id
                    if any(prefix in model_id.lower() for prefix in ['gpt-4', 'gpt-3.5']):
                        chat_models.append({
                            'id': model_id,
                            'name': model_id,
                            'created': getattr(model, 'created', 0)
                        })
                chat_models.sort(key=lambda x: x['created'], reverse=True)
                return chat_models
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return [
                {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini (default)', 'created': 0},
                {'id': 'gpt-4o', 'name': 'GPT-4o', 'created': 0},
                {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'created': 0},
                {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'created': 0},
            ]

    @classmethod
    @backoff.on_exception(
        backoff.expo, 
        (OpenAIError, ClientError), 
        max_tries=3, 
        jitter=backoff.random_jitter,
        max_time=60
    )
    async def responses_request(
        cls,
        chat_id: int,
        user_content: List[Dict[str, Any]],
        previous_response_id: str | None = None,
    ) -> str:
        """Вызов Responses API + учёт расхода токенов."""
        async with cls.RATE_LIMIT:
            logger.info("Запрос в OpenAI (chat=%s, prev=%s)", 
                       chat_id, previous_response_id)
            current_model = await cls.get_current_model()
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
            except openai.NotFoundError as e:
                # Обрабатываем 404 ошибку - скорее всего файл или response_id устарел
                error_message = str(e)
                if "Files" in error_message and "were not found" in error_message:
                    logger.warning(f"OpenAI файлы не найдены для чата {chat_id}: {error_message}")
                    logger.info("Очищаем историю чата и файлы, повторяем запрос без previous_response_id")
                    
                    # Очищаем историю чата и файлы
                    await cls.delete_files_by_chat(chat_id)
                    async with get_conn() as db:
                        await db.execute(
                            "DELETE FROM chat_history WHERE chat_id = ?",
                            (chat_id,)
                        )
                        await db.commit()
                    
                    # Повторяем запрос без previous_response_id (как новая сессия)
                    request_params_clean = {
                        "model": current_model,
                        "input": [
                            {
                                "type": "message",
                                "content": settings.system_prompt,
                                "role": "system"
                            }
                        ] + user_content,
                        "store": True
                    }
                    
                    logger.info("Повторный запрос без previous_response_id")
                    response = await client.responses.create(**request_params_clean)
                else:
                    logger.error(f"OpenAI NotFound error: {e}")
                    raise
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

    @classmethod
    async def dalle(cls, prompt: str, size: str, chat_id: int, user_id: int) -> str | None:
        """Генерирует изображение через OpenAI DALL·E и возвращает URL."""
        async with cls.RATE_LIMIT:
            try:
                # Используем официальный AsyncOpenAI для генерации изображения
                response = await client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size=size,
                    user=str(user_id)
                )
                # DALL·E 3 возвращает список изображений
                if response and hasattr(response, 'data') and response.data:
                    return response.data[0].url
                logger.error(f"DALL·E не вернул изображение: {response}")
                return None
            except Exception as e:
                logger.error(f"Ошибка генерации изображения DALL·E: {e}")
                return None

    @classmethod
    async def whisper(cls, audio_file: io.BytesIO, chat_id: int, user_id: int) -> str:
        """Распознаёт речь с помощью OpenAI Whisper и возвращает текст."""
        async with cls.RATE_LIMIT:
            try:
                logger.info(f"Отправка аудио в Whisper для chat_id={chat_id}, user_id={user_id}")
                audio_file.seek(0)
                transcript = await client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    response_format="text",
                    language="ru"
                )
                logger.info(f"Whisper результат: {transcript}")
                return transcript
            except Exception as e:
                logger.error(f"Ошибка Whisper: {e}")
                raise