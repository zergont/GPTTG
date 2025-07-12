"""Обработка документов → загрузка в OpenAI → анализ через Responses API."""
from aiogram import Router
from aiogram.types import Message, Document
from bot.config import settings
from bot.utils.openai_client import OpenAIClient
from bot.utils.http_client import download_file
from bot.utils.log import logger
import openai
import aiohttp

router = Router()

# Поддерживаемые типы документов
SUPPORTED_DOCUMENT_TYPES = {
    'application/pdf': '📄 PDF',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📝 Word документ',
    'application/msword': '📝 Word документ',
    'text/plain': '📄 Текстовый файл',
    'text/csv': '📊 CSV файл',
    'text/markdown': '📄 Markdown',
    'application/json': '📄 JSON файл',
}

@router.message(lambda m: m.document)
async def handle_document(msg: Message):
    """Обрабатывает загруженные документы через OpenAI Files API."""
    status_msg = None
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

        # Проверяем поддержку файла
        is_supported = (
            mime_type in SUPPORTED_DOCUMENT_TYPES or 
            file_extension in ['pdf', 'docx', 'doc', 'txt', 'csv', 'md', 'json']
        )

        if not is_supported:
            supported_list = "\n".join([f"• {name}" for name in SUPPORTED_DOCUMENT_TYPES.values()])
            await msg.reply(
                f"📄 **Неподдерживаемый тип файла.**\n\n"
                f"**Поддерживаются:**\n{supported_list}\n\n"
                f"💡 **Для других форматов:** конвертируйте в PDF или текст"
            )
            return

        file_type = SUPPORTED_DOCUMENT_TYPES.get(mime_type, f"📄 файл .{file_extension}")
        caption = msg.caption or "Проанализируй этот документ"

        # Получаем URL файла
        file = await msg.bot.get_file(doc.file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"

        status_msg = await msg.answer(f"📄 Загружаю {file_type} в OpenAI...")

        # Загружаем файл из Telegram
        data = await download_file(file_url)

        await status_msg.edit_text(f"📄 Обрабатываю {file_type}...")

        # Для текстовых файлов используем прямую передачу текста
        if mime_type in ['text/plain', 'text/csv', 'text/markdown', 'application/json']:
            try:
                # Пробуем декодировать как текст
                text_content = None
                for encoding in ['utf-8', 'utf-8-sig', 'cp1251', 'iso-8859-1']:
                    try:
                        text_content = data.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue

                if text_content is None:
                    raise UnicodeDecodeError("Не удалось декодировать файл")

                # Ограничиваем размер для экономии токенов
                if len(text_content) > 100000:
                    text_content = text_content[:100000] + "\n\n... (файл обрезан)"

                # Отправляем как обычное текстовое сообщение
                content = [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": f"{caption}\n\n**Файл:** {doc.file_name}\n**Содержимое:**\n```\n{text_content}\n```"}
                        ]
                    }
                ]

                response_text = await OpenAIClient.responses_request(msg.chat.id, content)

            except UnicodeDecodeError:
                # Если не удалось декодировать, загружаем как файл с purpose="user_data"
                file_id = await OpenAIClient.upload_file(data, doc.file_name, "user_data")

                content = [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_file", "file_id": file_id},
                            {"type": "input_text", "text": caption}
                        ]
                    }
                ]

                response_text = await OpenAIClient.responses_request(msg.chat.id, content)

        else:
            # Для PDF и Word документов загружаем файл в OpenAI с purpose="user_data"
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

        await status_msg.delete()

        # Отправляем результат
        result_text = f"📄 **Анализ файла {doc.file_name}:**\n\n{response_text}"

        # Если ответ слишком длинный, разбиваем на части
        if len(result_text) > 4000:
            await msg.answer(f"📄 **Анализ файла {doc.file_name}:**", parse_mode="Markdown")

            # Разбиваем ответ на куски
            chunks = [response_text[i:i+3800] for i in range(0, len(response_text), 3800)]
            for i, chunk in enumerate(chunks, 1):
                await msg.answer(f"**Часть {i}:**\n\n{chunk}", parse_mode="Markdown")
        else:
            await msg.answer(result_text, parse_mode="Markdown")

    except openai.BadRequestError as e:
        logger.error(f"Ошибка OpenAI при обработке файла: {e}")
        if status_msg:
            if "no text could be extracted" in str(e).lower():
                await status_msg.edit_text(
                    f"❌ Не удалось извлечь текст из файла.\n\n"
                    f"💡 **Возможные причины:**\n"
                    f"• Файл содержит только изображения (сканированный PDF)\n"
                    f"• Файл поврежден или зашифрован\n\n"
                    f"**Попробуйте:**\n"
                    f"• Сделать скриншоты страниц и отправить как изображения\n"
                    f"• Конвертировать в текстовый формат"
                )
            else:
                await status_msg.edit_text(f"❌ Ошибка обработки файла: {e}")
        else:
            await msg.answer(f"❌ Ошибка обработки файла: {e}")

    except aiohttp.ClientError as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        if status_msg:
            await status_msg.edit_text("❌ Ошибка загрузки файла. Попробуйте позже.")
        else:
            await msg.answer("❌ Ошибка загрузки файла. Попробуйте позже.")

    except openai.APITimeoutError:
        if status_msg:
            await status_msg.edit_text("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте ещё раз позже.")
        else:
            await msg.answer("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте ещё раз позже.")

    except Exception as e:
        logger.error(f"Ошибка при обработке документа: {e}", exc_info=True)
        try:
            if status_msg:
                await status_msg.edit_text(f"❌ Произошла непредвиденная ошибка: {str(e)[:100]}...")
            else:
                await msg.answer("❌ Произошла непредвиденная ошибка при обработке документа.")
        except Exception:
            await msg.answer("❌ Произошла непредвиденная ошибка при обработке документа.")