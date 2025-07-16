"""Голосовые сообщения → Whisper → текст → модель."""
from aiogram import Router
from aiogram.types import Message
import asyncio
from bot.config import settings
from bot.utils.openai_client import OpenAIClient
from bot.utils.db import get_conn
from bot.utils.http_client import download_file
from bot.utils.log import logger
from bot.utils.progress import show_progress_indicator
import io
import openai
import aiohttp

router = Router()

@router.message(lambda m: m.voice)
async def handle_voice(msg: Message):
    progress_task = None
    try:
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

        # Получаем ответ от модели
        content = [{"type": "message", "role": "user", "content": text}]
        response_text = await OpenAIClient.responses_request(msg.chat.id, content)
        await msg.answer(response_text)

    except aiohttp.ClientError as e:
        logger.error(f"Ошибка сети при загрузке голосового файла: {e}")
        await msg.answer("❌ Ошибка загрузки голосового файла. Попробуйте позже.")
    except openai.APITimeoutError:
        await msg.answer("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте ещё раз позже.")
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        await msg.answer(f"❌ Произошла ошибка: {str(e)[:100]}...")
    finally:
        # Гарантированно отменяем задачу индикации
        if progress_task and not progress_task.done():
            progress_task.cancel()