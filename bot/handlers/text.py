"""Обработка обычных текстовых сообщений."""
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from bot.utils.db import get_conn
from bot.utils.openai import OpenAIClient
from bot.utils.progress import show_progress_indicator
from bot.utils.errors import error_handler
from bot.utils.datetime_context import enhance_content_dict_with_datetime

router = Router()

@router.message(lambda msg: msg.text and not msg.text.startswith('/'))
@error_handler("text_handler")
async def handle_text(msg: Message):
    """Обработка текстовых сообщений с индикатором прогресса и веб-поиском."""
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

        # Добавляем временной контекст
        content[0] = enhance_content_dict_with_datetime(content[0])

        # Включаем веб-поиск для всех текстовых сообщений
        # Больше не передаем tools - используем enable_web_search

        # Вызов OpenAI API с передачей previous_response_id и включением веб-поиска
        response_text = await OpenAIClient.responses_request(
            msg.chat.id,
            content,
            prev_id,  # Важно! Передаем previous_response_id для экономии токенов
            enable_web_search=True  # Включаем веб-поиск
        )
        
        # Отправляем фактический ответ
        await msg.answer(response_text)
        
    finally:
        # Гарантированно отменяем задачу индикации
        if progress_task and not progress_task.done():
            progress_task.cancel()
