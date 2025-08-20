"""Обработка обычных текстовых сообщений."""
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from bot.utils.db import get_conn
from bot.utils.openai import OpenAIClient
from bot.utils.progress import show_progress_indicator
from bot.utils.errors import error_handler
from bot.utils.datetime_context import enhance_content_dict_with_datetime
from bot.utils.html import send_long_html_message, escape_html

router = Router()

@router.message(lambda msg: msg.text and not msg.text.startswith('/'))
@error_handler("text_handler")
async def handle_text(msg: Message):
    """Обработка текстовых сообщений с индикатором прогресса и веб-поиском."""
    async with get_conn() as db:
        cur = await db.execute(
            "SELECT last_response FROM chat_history WHERE chat_id = ?",
            (msg.chat.id,)
        )
        row = await cur.fetchone()
        prev_id = row[0] if row else None

    progress_task = asyncio.create_task(show_progress_indicator(msg.bot, msg.chat.id))

    try:
        content = [{
            "type": "message",
            "role": "user", 
            "content": msg.text
        }]
        # Добавляем временной контекст с учётом TZ пользователя
        content[0] = await enhance_content_dict_with_datetime(content[0], msg.from_user.id)

        response_text = await OpenAIClient.responses_request(
            msg.chat.id,
            msg.from_user.id,
            content,
            prev_id,
            enable_web_search=True
        )
        safe_text = escape_html(response_text or "")
        await send_long_html_message(msg, safe_text)
    finally:
        if progress_task and not progress_task.done():
            progress_task.cancel()
