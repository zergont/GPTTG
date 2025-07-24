"""Обработка документов → загрузка в OpenAI → анализ через Responses API."""
from aiogram import Router
from aiogram.types import Message, Document
import asyncio
from bot.config import settings
from bot.utils.openai_client import OpenAIClient
from bot.utils.http_client import download_file
from bot.utils.log import logger
from bot.utils.progress import show_progress_indicator
import openai
import aiohttp

router = Router()

# Поддерживаемые типы документов (только PDF)
SUPPORTED_DOCUMENT_TYPES = {
    'application/pdf': '📄 PDF',
}

@router.message(lambda m: m.document)
async def handle_document(msg: Message):
    """Обрабатывает загруженные документы через OpenAI Files API с явной индикацией загрузки и анализа."""
    upload_task = None
    analyze_task = None
    try:
        doc: Document = msg.document

        # Проверяем размер файла (OpenAI лимит 512 МБ, но для бота ставим меньше)
        max_size_mb = min(settings.max_file_mb, 100)  # Максимум 100 МБ
        if doc.file_size > max_size_mb * 1024 * 1024:
            await msg.reply(f"📄 Файл слишком большой (>{max_size_mb} МБ)")
            return

        # Проверяем тип файла
        mime_type = doc.mime_type
        file_extension = doc.file_name.lower().split('.')[-1] if doc.file_name else ''

        # Разрешаем только PDF
        is_supported = mime_type == 'application/pdf' or file_extension == 'pdf'

        if not is_supported:
            await msg.reply(
                "📄 **Неподдерживаемый тип файла.**\n\n"
                "**Поддерживается только PDF-документ.**\n\n"
                "💡 Для других форматов: конвертируйте файл в PDF."
            )
            return

        file_type = SUPPORTED_DOCUMENT_TYPES.get(mime_type, f"📄 файл .{file_extension}")
        caption = msg.caption or "Проанализируй этот документ"

        # Получаем URL файла
        file = await msg.bot.get_file(doc.file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"

        # Индикатор загрузки файла
        upload_task = asyncio.create_task(
            show_progress_indicator(msg.bot, msg.chat.id, max_time=120, message="📥 Загружаю документ")
        )
        try:
            # Загружаем файл из Telegram
            data = await download_file(file_url)

            # Загружаем PDF-файл в OpenAI с purpose="user_data"
            file_id = await OpenAIClient.upload_file(data, doc.file_name, "user_data", chat_id=msg.chat.id)
        except Exception as e:
            if upload_task and not upload_task.done():
                upload_task.cancel()
            await msg.answer(f"❌ Ошибка загрузки файла: {e}")
            return
        if upload_task and not upload_task.done():
            upload_task.cancel()

        # Индикатор анализа документа
        analyze_task = asyncio.create_task(
            show_progress_indicator(msg.bot, msg.chat.id, max_time=180, message="🔍 Анализирую документ")
        )

        # Формируем запрос с файлом и текстом
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

        try:
            response_text = await OpenAIClient.responses_request(msg.chat.id, content)
        except Exception as e:
            if analyze_task and not analyze_task.done():
                analyze_task.cancel()
            await msg.answer(f"❌ Ошибка анализа документа: {e}")
            return
        if analyze_task and not analyze_task.done():
            analyze_task.cancel()

        # Отправляем результат БЕЗ MarkdownV2 - используем обычный текст
        result_text = f"📄 Анализ файла {doc.file_name}:\n\n{response_text}"
        
        # Разбиваем на части если нужно
        if len(result_text) <= 4096:
            await msg.answer(result_text)
        else:
            # Разбиваем на части вручную без экранирования
            chunks = []
            current_pos = 0
            max_length = 4096
            
            while current_pos < len(result_text):
                end_pos = current_pos + max_length
                if end_pos >= len(result_text):
                    chunks.append(result_text[current_pos:])
                    break
                
                # Ищем удобное место для разрыва
                safe_break = result_text.rfind('\n', current_pos, end_pos)
                if safe_break == -1 or safe_break == current_pos:
                    safe_break = result_text.rfind(' ', current_pos, end_pos)
                if safe_break == -1 or safe_break == current_pos:
                    safe_break = end_pos
                
                chunks.append(result_text[current_pos:safe_break])
                current_pos = safe_break + (1 if result_text[safe_break:safe_break+1] in ['\n', ' '] else 0)
            
            for chunk in chunks:
                await msg.answer(chunk)

    except Exception as e:
        if upload_task and not upload_task.done():
            upload_task.cancel()
        if analyze_task and not analyze_task.done():
            analyze_task.cancel()
        logger.error(f"Ошибка при обработке документа: {e}", exc_info=True)
        try:
            await msg.answer("❌ Произошла непредвиденная ошибка при обработке документа.")
        except Exception:
            pass