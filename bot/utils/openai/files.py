"""Управление файлами OpenAI."""
import io
import openai
from bot.utils.log import logger
from .base import client, oai_limiter


class FilesManager:
    """Управление файлами OpenAI."""
    
    @staticmethod
    async def upload_file(file_data: bytes, filename: str, purpose: str = "user_data", chat_id: int | None = None) -> str:
        """Загружает файл в OpenAI, возвращает file_id и сохраняет его в БД если chat_id указан."""
        async with oai_limiter(chat_id):
            logger.info(f"Загружаем файл {filename} в OpenAI")
            file_obj = io.BytesIO(file_data)
            file_obj.name = filename
            try:
                file_response = await client.files.create(
                    file=file_obj,
                    purpose=purpose
                )
                logger.info(f"Файл загружен с ID: {file_response.id}")
                
                if chat_id is not None:
                    from bot.utils.db import save_openai_file_id
                    await save_openai_file_id(chat_id, file_response.id)
                
                from bot.config import settings
                if getattr(settings, "debug_mode", False):
                    logger.info(f"[DEBUG] UPLOAD FILE RESPONSE: {file_response}")
                
                return file_response.id
            except openai.BadRequestError as e:
                logger.error(f"Ошибка формата при загрузке файла: {e}")
                raise
            except openai.AuthenticationError as e:
                logger.error(f"Ошибка аутентификации: {e}")
                raise
            except Exception as e:
                logger.error(f"Непредвиденная ошибка загрузки файла: {e}")
                raise

    @staticmethod
    async def delete_files_by_chat(chat_id: int):
        """Удаляет все файлы, загруженные этим чатом в OpenAI, и очищает их из БД."""
        from bot.utils.db import get_openai_file_ids_by_chat, delete_openai_file_ids_by_chat
        
        file_ids = await get_openai_file_ids_by_chat(chat_id)
        deleted = 0
        
        for file_id in file_ids:
            try:
                await client.files.delete(file_id)
                deleted += 1
            except Exception as e:
                logger.error(f"Ошибка удаления файла {file_id} из OpenAI: {e}")
        
        await delete_openai_file_ids_by_chat(chat_id)
        logger.info(f"Удалено {deleted} файлов OpenAI для чата {chat_id}")