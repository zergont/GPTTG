"""Простые middlewares: инициализация БД и глобальный обработчик ошибок."""
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from bot.utils.log import logger
from bot.utils.db import init_db, save_user, mark_user_welcomed
from bot.keyboards import main_kb
from bot.config import settings


class StartupMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data):
        # Создаём/инициализируем БД один раз
        await init_db()
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
    async def __call__(self, handler, event: TelegramObject, data):
        try:
            return await handler(event, data)
        except Exception as e:  # noqa: BLE001
            logger.exception("Необработанная ошибка: %s", e)
            
            # Пытаемся отправить сообщение об ошибке пользователю
            if hasattr(event, "answer"):
                try:
                    await event.answer("⚠️ На сервере произошла ошибка. Сообщите администратору.")
                except Exception as reply_error:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {reply_error}")
            
            # НЕ прерываем работу бота - просто логируем ошибку и продолжаем
            # return None позволяет боту продолжить работу
            return None