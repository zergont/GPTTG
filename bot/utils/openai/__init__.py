"""Модульный OpenAI клиент с разделением по функциональности."""

# Импортируем все менеджеры
from .models import ModelsManager
from .files import FilesManager
from .chat import ChatManager
from .dalle import DalleManager
from .whisper import WhisperManager

# Для обратной совместимости создаем класс-обертку
class OpenAIClient:
    """
    Объединенный клиент для работы с OpenAI API.
    
    Этот класс обеспечивает обратную совместимость с существующим кодом,
    при этом внутренне используя модульную архитектуру.
    """
    
    # Модели
    @staticmethod
    async def get_current_model() -> str:
        """Получает текущую активную модель."""
        return await ModelsManager.get_current_model()
    
    @staticmethod
    async def set_current_model(model: str) -> None:
        """Устанавливает текущую модель."""
        await ModelsManager.set_current_model(model)
    
    @staticmethod
    async def get_available_models():
        """Получает список доступных моделей."""
        return await ModelsManager.get_available_models()
    
    # Файлы
    @staticmethod
    async def upload_file(file_data: bytes, filename: str, purpose: str = "user_data", chat_id: int | None = None) -> str:
        """Загружает файл в OpenAI."""
        return await FilesManager.upload_file(file_data, filename, purpose, chat_id)
    
    @staticmethod
    async def delete_files_by_chat(chat_id: int):
        """Удаляет файлы чата из OpenAI."""
        await FilesManager.delete_files_by_chat(chat_id)
    
    # Чат
    @staticmethod
    async def responses_request(chat_id: int, user_content, previous_response_id: str | None = None, tools: list | None = None) -> str:
        """Отправляет запрос в Responses API."""
        return await ChatManager.responses_request(chat_id, user_content, previous_response_id, tools=tools)
    
    # DALL-E
    @staticmethod
    async def dalle(prompt: str, size: str, chat_id: int, user_id: int) -> str | None:
        """Генерирует изображение через DALL-E."""
        return await DalleManager.generate_image(prompt, size, chat_id, user_id)
    
    # Whisper
    @staticmethod
    async def whisper(audio_file, chat_id: int, user_id: int) -> str:
        """Распознает речь через Whisper."""
        return await WhisperManager.transcribe_audio(audio_file, chat_id, user_id)


# Экспортируем для прямого использования
__all__ = [
    'OpenAIClient',
    'ModelsManager', 
    'FilesManager',
    'ChatManager',
    'DalleManager',
    'WhisperManager'
]