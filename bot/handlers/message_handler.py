"""Обработчики текстовых сообщений бота."""
import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

from bot.utils.openai_client import OpenAIClient
from bot.utils.log import logger
from bot.utils.progress import show_progress_indicator
import openai

# Создаем роутер для этого обработчика
router = Router()

@router.message(lambda msg: msg.text and not msg.text.startswith('/'))
async def handle_message(msg: Message):
    """Обработчик текстовых сообщений для aiogram 3.x."""
    # Получение текста сообщения
    message_text = msg.text
    
    # Запускаем фоновую задачу индикации
    progress_task = asyncio.create_task(show_progress_indicator(msg.bot, msg.chat.id))
    
    try:
        # Вызов OpenAI API может занимать время
        response = await OpenAIClient.responses_request(
            chat_id=msg.chat.id,
            user_content=[{"type": "message", "content": message_text, "role": "user"}]
        )
        
        # Отменяем задачу индикации после получения ответа
        progress_task.cancel()
        
        # Отправляем фактический ответ
        await msg.answer(response)
    except openai.APITimeoutError:
        # Отменяем задачу индикации и отправляем сообщение об ошибке
        progress_task.cancel()
        await msg.answer("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте повторить запрос.")
    except openai.RateLimitError:
        progress_task.cancel()
        await msg.answer("🔄 Превышен лимит запросов. Пожалуйста, повторите через несколько минут.")
    except Exception as e:
        # Отменяем задачу индикации в случае других ошибок
        progress_task.cancel()
        error_message = f"❌ Произошла ошибка: {str(e)[:100]}..."
        await msg.answer(error_message)
        logger.error(f"Ошибка при обработке сообщения: {e}")