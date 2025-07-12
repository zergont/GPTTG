"""Обработка обычных текстовых сообщений."""
from aiogram import Router, F
from aiogram.types import Message
from bot.utils.db import get_conn
from bot.utils.openai_client import OpenAIClient
from bot.utils.log import logger

router = Router()

@router.message(F.text)
async def handle_text(msg: Message):
    """Обработка текстовых сообщений."""
    # Получаем previous_response_id из базы
    async with get_conn() as db:
        cur = await db.execute(
            "SELECT last_response FROM chat_history WHERE chat_id = ?",
            (msg.chat.id,)
        )
        row = await cur.fetchone()
        prev_id = row[0] if row else None

    # Формируем контент в правильном формате для Responses API
    content = [{
        "type": "message",
        "role": "user",
        "content": msg.text
    }]

    try:
        response_text = await OpenAIClient.responses_request(
            msg.chat.id,
            content,
            prev_id
        )
        
        await msg.answer(response_text)
    except Exception as e:
        logger.error(f"Ошибка при обработке текста: {e}")
        await msg.answer(f"Произошла ошибка: {str(e)}")
