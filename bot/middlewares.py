"""Простые middlewares: инициализация БД и глобальный обработчик ошибок."""
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from bot.utils.log import logger
from bot.utils.db import init_db, save_user, mark_user_welcomed
from bot.utils.errors import ErrorHandler
from bot.keyboards import main_kb
from bot.config import settings


class StartupMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data):
        # Больше не инициализируем БД здесь!
        return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """Middleware для обработки пользователей и приветственных сообщений."""
    
    async def __call__(self, handler, event: TelegramObject, data):
        # Обрабатываем только сообщения от пользователей
        if isinstance(event, Message) and event.from_user:
            is_new_user = await save_user(event.from_user)
            
            if is_new_user:
                # Отправляем приветственное сообщение
                welcome_text = (
                    f"👋 Добро пожаловать, {event.from_user.first_name or 'друг'}!\n\n"
                    f"Я — умный ассистент, использующий новый OpenAI Responses API. "
                    f"Могу:\n\n"
                    f"💬 Отвечать на ваши вопросы\n"
                    f"🖼 Анализировать изображения\n"
                    f"🎤 Распознавать голосовые сообщения\n"
                    f"🎨 Генерировать картинки по описанию\n\n"
                    f"Начните общение или воспользуйтесь командой /help для справки!"
                )
                
                try:
                    await event.answer(
                        welcome_text, 
                        reply_markup=main_kb(event.from_user.id == settings.admin_id)
                    )
                    await mark_user_welcomed(event.from_user.id)
                    logger.info(f"Отправлено приветствие пользователю {event.from_user.id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки приветствия: {e}")
        
        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    """Глобальный middleware для обработки необработанных ошибок."""
    
    async def __call__(self, handler, event: TelegramObject, data):
        try:
            return await handler(event, data)
        except Exception as e:
            # Используем централизованную систему обработки ошибок
            message = None
            callback = None
            
            if isinstance(event, Message):
                message = event
            elif isinstance(event, CallbackQuery):
                callback = event
                
            await ErrorHandler.handle_error(
                e, 
                message=message, 
                callback=callback, 
                context="global_middleware"
            )
            
            # НЕ прерываем работу бота - просто обрабатываем ошибку и продолжаем
            return None