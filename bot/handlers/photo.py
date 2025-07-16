"""Фото с подписью → мультимодальный запрос."""
from aiogram import Router
from aiogram.types import Message
import asyncio
from bot.config import settings
from bot.utils.openai_client import OpenAIClient
from bot.utils.db import get_conn
from bot.utils.log import logger
from bot.utils.progress import show_progress_indicator
import openai

router = Router()


@router.message(lambda m: m.photo)
async def handle_photo(msg: Message):
    progress_task = None
    try:
        caption = msg.caption or "Опиши изображение"
        # Берём самое большое фото
        largest = max(msg.photo, key=lambda p: p.file_size)
        if largest.file_size > settings.max_file_mb * 1024 * 1024:
            await msg.reply("Файл слишком большой (>20 МБ)")
            return

        # Получаем URL файла
        file = await msg.bot.get_file(largest.file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"

        # Получаем previous_response_id из базы
        async with get_conn() as db:
            row = await (await db.execute(
                "SELECT last_response FROM chat_history WHERE chat_id = ?", (msg.chat.id,)
            )).fetchone()
        prev_id = row[0] if row else None

        # Формируем контент для Responses API
        content = [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": caption},
                    {"type": "input_image", "image_url": file_url}
                ]
            }
        ]

        # Запускаем индикатор прогресса
        progress_task = asyncio.create_task(
            show_progress_indicator(msg.bot, msg.chat.id)
        )

        response_text = await OpenAIClient.responses_request(msg.chat.id, content, prev_id)
        await msg.answer(response_text)
        
    except openai.APITimeoutError:
        await msg.answer("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте ещё раз позже.")
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        await msg.answer(f"❌ Произошла ошибка при обработке изображения: {e}")
    finally:
        # Гарантированно отменяем задачу индикации
        if progress_task and not progress_task.done():
            progress_task.cancel()