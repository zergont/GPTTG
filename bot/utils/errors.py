"""Централизованная система обработки ошибок."""
import traceback
from typing import Optional, Any, Callable, Awaitable
from functools import wraps
from aiogram.types import Message, CallbackQuery
import openai

from bot.utils.log import logger


class ErrorType:
    """Типы ошибок с пользовательскими сообщениями."""
    
    # OpenAI API ошибки
    OPENAI_TIMEOUT = ("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте ещё раз позже.", 
                      "OpenAI API timeout")
    OPENAI_RATE_LIMIT = ("🔄 Превышен лимит запросов. Пожалуйста, повторите через несколько минут.", 
                         "OpenAI rate limit exceeded")
    OPENAI_AUTH = ("🔐 Ошибка авторизации OpenAI. Обратитесь к администратору.", 
                   "OpenAI authentication error")
    OPENAI_BAD_REQUEST = ("❌ Некорректный запрос к OpenAI. Попробуйте перефразировать.", 
                          "OpenAI bad request")
    OPENAI_NOT_FOUND = ("🔍 Данные не найдены. История чата сброшена.", 
                        "OpenAI resource not found")
    
    # Файловые ошибки
    FILE_TOO_LARGE = ("📁 Файл слишком большой. Максимальный размер: {} МБ", 
                      "File too large")
    FILE_UNSUPPORTED = ("📄 Неподдерживаемый тип файла. Поддерживаются: PDF, изображения", 
                        "Unsupported file type")
    FILE_DOWNLOAD_ERROR = ("📥 Ошибка загрузки файла. Попробуйте ещё раз.", 
                           "File download error")
    
    # Сетевые ошибки
    NETWORK_ERROR = ("🌐 Проблемы с сетью. Проверьте подключение и попробуйте позже.", 
                     "Network connection error")
    
    # Общие ошибки
    UNKNOWN_ERROR = ("❌ Произошла непредвиденная ошибка. Попробуйте ещё раз.", 
                     "Unknown error occurred")
    PERMISSION_DENIED = ("🚫 Недостаточно прав для выполнения этой команды.", 
                         "Permission denied")


class ErrorHandler:
    """Централизованный обработчик ошибок."""
    
    @staticmethod
    def _get_error_info(exception: Exception) -> tuple[str, str]:
        """Определяет тип ошибки и возвращает пользовательское и техническое сообщение."""
        
        # OpenAI ошибки
        if isinstance(exception, openai.APITimeoutError):
            return ErrorType.OPENAI_TIMEOUT
        elif isinstance(exception, openai.RateLimitError):
            return ErrorType.OPENAI_RATE_LIMIT
        elif isinstance(exception, openai.AuthenticationError):
            return ErrorType.OPENAI_AUTH
        elif isinstance(exception, openai.BadRequestError):
            return ErrorType.OPENAI_BAD_REQUEST
        elif isinstance(exception, openai.NotFoundError):
            return ErrorType.OPENAI_NOT_FOUND
        
        # Сетевые ошибки
        elif "ClientError" in str(type(exception).__name__) or "aiohttp" in str(type(exception).__module__ or ""):
            return ErrorType.NETWORK_ERROR
        
        # Файловые ошибки (определяются по сообщению)
        elif "too large" in str(exception).lower() or "большой" in str(exception).lower():
            return ErrorType.FILE_TOO_LARGE
        elif "unsupported" in str(exception).lower() or "неподдерживаемый" in str(exception).lower():
            return ErrorType.FILE_UNSUPPORTED
        
        # Общие ошибки
        else:
            return ErrorType.UNKNOWN_ERROR
    
    @staticmethod
    async def handle_error(
        exception: Exception, 
        message: Optional[Message] = None,
        callback: Optional[CallbackQuery] = None,
        context: str = "unknown"
    ) -> None:
        """
        Обрабатывает ошибку и отправляет пользователю понятное сообщение.
        
        Args:
            exception: Исключение для обработки
            message: Сообщение для ответа (приоритет)
            callback: Callback для ответа (если message не указан)
            context: Контекст ошибки для логирования
        """
        
        user_message, tech_description = ErrorHandler._get_error_info(exception)
        
        # Логируем техническую информацию
        logger.error(
            f"Error in {context}: {tech_description} - {str(exception)}", 
            exc_info=True
        )
        
        # Отправляем пользователю понятное сообщение
        try:
            if message:
                await message.answer(user_message)
            elif callback:
                await callback.message.answer(user_message)
                await callback.answer("❌ Произошла ошибка", show_alert=True)
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")
    
    @staticmethod
    def error_handler(context: str = "handler"):
        """
        Декоратор для автоматической обработки ошибок в handlers.
        
        Args:
            context: Описание контекста для логирования
        """
        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # Попытаемся найти Message или CallbackQuery в аргументах
                    message = None
                    callback = None
                    
                    for arg in args:
                        if isinstance(arg, Message):
                            message = arg
                            break
                        elif isinstance(arg, CallbackQuery):
                            callback = arg
                            break
                    
                    await ErrorHandler.handle_error(e, message, callback, f"{context}:{func.__name__}")
                    return None
            
            return wrapper
        return decorator


# Удобные алиасы
handle_error = ErrorHandler.handle_error
error_handler = ErrorHandler.error_handler

__all__ = ['ErrorHandler', 'ErrorType', 'handle_error', 'error_handler']