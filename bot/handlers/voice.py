"""Голосовые сообщения → Whisper → текст → модель."""
from aiogram import Router
from aiogram.types import Message
import asyncio
import io
import math

from bot.config import settings
from bot.utils.openai import OpenAIClient
from bot.utils.http_client import download_file
from bot.utils.progress import show_progress_indicator
from bot.utils.errors import error_handler
from bot.utils.datetime_context import enhance_content_dict_with_datetime
from bot.utils.db import get_conn

router = Router()

@router.message(lambda m: m.voice)
@error_handler("voice_handler")
async def handle_voice(msg: Message):
    v = msg.voice
    if v.file_size > settings.max_file_mb * 1024 * 1024:
        await msg.reply(f"Файл слишком большой (>{settings.max_file_mb} МБ)")
        return

    file = await msg.bot.get_file(v.file_id)
    url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"

    # Запускаем индикатор прогресса
    progress_task = asyncio.create_task(
        show_progress_indicator(msg.bot, msg.chat.id)
    )
    
    try:
        # Загружаем файл
        data = await download_file(url)
        
        audio_file = io.BytesIO(data)
        audio_file.name = "voice.ogg"

        # Расшифровываем через Whisper
        text = await OpenAIClient.whisper(audio_file, msg.chat.id, msg.from_user.id)
        
        if not text.strip():
            await msg.answer("❌ Не удалось распознать речь в голосовом сообщении")
            return

        await msg.answer(f"🗣 Вы сказали: {text}")

        # Учёт расходов Whisper: стоимость за полные минуты
        minutes = max(1, math.ceil((v.duration or 0) / 60))
        cost = minutes * settings.whisper_price
        async with get_conn() as db:
            await db.execute(
                "INSERT INTO usage(chat_id, user_id, tokens, cost, model) VALUES (?, ?, ?, ?, ?)",
                (msg.chat.id, msg.from_user.id, 0, cost, "whisper-1")
            )
            await db.commit()

        # Получаем ответ от модели с веб-поиском
        content = [{"type": "message", "role": "user", "content": text}]
        
        # Добавляем временной контекст (TZ пользователя)
        content[0] = await enhance_content_dict_with_datetime(content[0], msg.from_user.id)
        
        response_text = await OpenAIClient.responses_request(
            msg.chat.id, 
            msg.from_user.id,
            content,
            enable_web_search=True  # Включаем веб-поиск
        )
        await msg.answer(response_text)

    finally:
        # Гарантированно отменяем задачу индикации
        if progress_task and not progress_task.done():
            progress_task.cancel()