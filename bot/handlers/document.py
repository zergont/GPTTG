"""Обработка документов → загрузка в OpenAI → анализ через Responses API."""
from aiogram import Router
from aiogram.types import Message, Document
import asyncio
from bot.config import settings
from bot.utils.openai import OpenAIClient
from bot.utils.http_client import download_file
from bot.utils.progress import show_progress_indicator
from bot.utils.html import send_long_html_message, escape_html
from bot.utils.errors import error_handler
from bot.utils.datetime_context import enhance_content_dict_with_datetime

router = Router()

SUPPORTED_DOCUMENT_TYPES = {
    'application/pdf': '📄 PDF',
}

@router.message(lambda m: m.document)
@error_handler("document_handler")
async def handle_document(msg: Message):
    upload_task = None
    analyze_task = None
    
    try:
        doc: Document = msg.document
        max_size_mb = min(settings.max_file_mb, 100)
        if doc.file_size > max_size_mb * 1024 * 1024:
            await msg.reply(f"📄 Файл слишком большой (>{max_size_mb} МБ)")
            return

        mime_type = doc.mime_type
        file_extension = doc.file_name.lower().split('.')[-1] if doc.file_name else ''
        is_supported = mime_type == 'application/pdf' or file_extension == 'pdf'
        if not is_supported:
            await msg.reply(
                "📄 <b>Неподдерживаемый тип файла.</b>\n\n"
                "<b>Поддерживается только PDF-документ.</b>\n\n"
                "💡 Для других форматов: конвертируйте файл в PDF.",
                parse_mode="HTML"
            )
            return

        caption = msg.caption or "Проанализируй этот документ"
        file = await msg.bot.get_file(doc.file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"

        upload_task = asyncio.create_task(
            show_progress_indicator(msg.bot, msg.chat.id, max_time=120, message="📥 Загружаю документ")
        )
        data = await download_file(file_url)

        file_id = await OpenAIClient.upload_file(data, doc.file_name, "user_data", chat_id=msg.chat.id)
        if upload_task and not upload_task.done():
            upload_task.cancel()

        analyze_task = asyncio.create_task(
            show_progress_indicator(msg.bot, msg.chat.id, max_time=180, message="🔍 Анализирую документ")
        )

        content = [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": file_id},
                    {"type": "input_text", "text": f"{caption}\n\nФайл: {doc.file_name}"}
                ]
            }
        ]
        content[0] = await enhance_content_dict_with_datetime(content[0], msg.from_user.id)

        response_text = await OpenAIClient.responses_request(
            msg.chat.id, 
            msg.from_user.id,
            content,
            enable_web_search=True
        )
        
        safe_response = escape_html(response_text or "")
        result_text = f"📄 <b>Анализ файла {escape_html(doc.file_name or '')}:</b>\n\n{safe_response}"
        await send_long_html_message(msg, result_text)
    finally:
        if upload_task and not upload_task.done():
            upload_task.cancel()
        if analyze_task and not analyze_task.done():
            analyze_task.cancel()