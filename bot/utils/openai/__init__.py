"""Модульный OpenAI клиент с разделением по функциональности."""

from .models import ModelsManager
from .files import FilesManager
from .chat import ChatManager
from .dalle import DalleManager
from .whisper import WhisperManager


class OpenAIClient:
    """Объединенный клиент для работы с OpenAI API."""
    
    # Делегируем все методы соответствующим менеджерам
    get_current_model = staticmethod(ModelsManager.get_current_model)
    set_current_model = staticmethod(ModelsManager.set_current_model)
    get_available_models = staticmethod(ModelsManager.get_available_models)
    
    upload_file = staticmethod(FilesManager.upload_file)
    delete_files_by_chat = staticmethod(FilesManager.delete_files_by_chat)
    
    responses_request = staticmethod(ChatManager.responses_request)
    
    dalle = staticmethod(DalleManager.generate_image)
    
    whisper = staticmethod(WhisperManager.transcribe_audio)


__all__ = [
    'OpenAIClient',
    'ModelsManager', 
    'FilesManager',
    'ChatManager',
    'DalleManager',
    'WhisperManager'
]