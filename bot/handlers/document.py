"""Обработка документов → загрузка в OpenAI → анализ через Responses API."""
from aiogram import Router
from aiogram.types import Message, Document
import asyncio
from bot.config import settings
from bot.utils.openai_client import OpenAIClient
from bot.utils.http_client import download_file
from bot.utils.log import logger
from bot.utils.markdown import escape_markdown_v2
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
    """Обрабатывает загруженные документы через OpenAI Files API."""
    progress_task = None
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

        # Запускаем индикатор прогресса вместо статического сообщения
        progress_task = asyncio.create_task(
            show_progress_indicator(msg.bot, msg.chat.id, max_time=180)  # Больше времени для PDF
        )

        # Загружаем файл из Telegram
        data = await download_file(file_url)

        # Загружаем PDF-файл в OpenAI с purpose="user_data"
        file_id = await OpenAIClient.upload_file(data, doc.file_name, "user_data")

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

        response_text = await OpenAIClient.responses_request(msg.chat.id, content)

        # Отправляем результат
        result_text = f"📄 **Анализ файла {doc.file_name}:**\n\n{response_text}"

        # Экранируем текст для MarkdownV2
        safe_text = escape_markdown_v2(result_text)
        MAX_LEN = 4096
        for i in range(0, len(safe_text), MAX_LEN):
            await msg.answer(safe_text[i:i+MAX_LEN], parse_mode="MarkdownV2")

    except openai.BadRequestError as e:
        logger.error(f"Ошибка OpenAI при обработке файла: {e}")
        if "no text could be extracted" in str(e).lower():
            await msg.answer(
                f"❌ Не удалось извлечь текст из файла.\n\n"
                f"💡 **Возможные причины:**\n"
                f"• Файл содержит только изображения (сканированный PDF)\n"
                f"• Файл поврежден или зашифрован\n\n"
                f"**Попробуйте:**\n"
                f"• Сделать скриншоты страниц и отправить как изображения\n"
                f"• Конвертировать в текстовый формат"
            )
        else:
            await msg.answer(f"❌ Ошибка обработки файла: {e}")

    except aiohttp.ClientError as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        await msg.answer("❌ Ошибка загрузки файла. Попробуйте позже.")

    except openai.APITimeoutError:
        await msg.answer("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте ещё раз позже.")

    except Exception as e:
        logger.error(f"Ошибка при обработке документа: {e}", exc_info=True)
        try:
            await msg.answer("❌ Произошла непредвиденная ошибка при обработке документа.")
        except Exception:
            pass
    finally:
        # Гарантированно отменяем задачу индикации
        if progress_task and not progress_task.done():
            progress_task.cancel()