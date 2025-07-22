"""Обработка обычных текстовых сообщений."""
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from bot.utils.db import get_conn
from bot.utils.openai_client import OpenAIClient
from bot.utils.log import logger
from bot.utils.progress import show_progress_indicator
import openai

router = Router()

@router.message(lambda msg: msg.text and not msg.text.startswith('/'))
async def handle_text(msg: Message):
    """Обработка текстовых сообщений с индикатором прогресса."""
    # Получаем previous_response_id из базы
    async with get_conn() as db:
        cur = await db.execute(
            "SELECT last_response FROM chat_history WHERE chat_id = ?",
            (msg.chat.id,)
        )
        row = await cur.fetchone()
        prev_id = row[0] if row else None

    # Запускаем фоновую задачу индикации
    progress_task = asyncio.create_task(show_progress_indicator(msg.bot, msg.chat.id))

    try:
        # Формируем контент в правильном формате для Responses API
        content = [{
            "type": "message",
            "role": "user", 
            "content": msg.text
        }]

        # Вызов OpenAI API с передачей previous_response_id
        response_text = await OpenAIClient.responses_request(
            msg.chat.id,
            content,
            prev_id  # Важно! Передаем previous_response_id для экономии токенов
        )
        
        # Отменяем задачу индикации после получения ответа
        progress_task.cancel()
        
        # Отправляем фактический ответ
        await msg.answer(response_text)
        
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
        logger.error(f"Ошибка при обработке текстового сообщения: {e}")
