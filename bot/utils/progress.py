"""Утилиты для отображения индикаторов прогресса."""

import asyncio
from bot.utils.log import logger
from bot.config import settings

async def show_progress_indicator(bot, chat_id, max_time: int | None = None, interval=2, message="Обрабатываю ваш запрос"):
    """
    Показывает индикатор загрузки для aiogram 3.x
    
    Args:
        bot: Экземпляр бота aiogram
        chat_id: ID чата для отправки сообщения
        max_time: Максимальное время ожидания в секундах
        interval: Интервал обновления индикатора в секундах
        message: Текст сообщения для отображения
    """
    indicators = ["⏳", "🔄", "⌛", "🤔", "💭", "🧠"]
    waiting_msg = None
    
    # Если max_time не задан — вычисляем умный дефолт: таймаут OpenAI + 30 сек буфера
    if max_time is None:
        try:
            max_time = int(getattr(settings, "openai_timeout_seconds", 180)) + 30
        except Exception:
            max_time = 210
    
    try:
        # Сначала отправляем сообщение о начале обработки
        waiting_msg = await bot.send_message(
            chat_id=chat_id, 
            text=f"{message}... ⏳"
        )
        
        # Затем периодически обновляем его, чтобы показать прогресс
        max_cycles = max(1, max_time // interval)
        for i in range(max_cycles):
            await asyncio.sleep(interval)
            current_indicator = indicators[i % len(indicators)]
            seconds = (i + 1) * interval
            
            # Обновляем сообщение разными индикаторами
            await bot.edit_message_text(
                text=f"{message}... {current_indicator}\n"
                     f"Прошло {seconds} сек. Пожалуйста, подождите.",
                chat_id=chat_id,
                message_id=waiting_msg.message_id
            )
    except asyncio.CancelledError:
        # Задача была отменена, значит ответ готов
        if waiting_msg:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=waiting_msg.message_id)
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Ошибка в индикаторе прогресса: {e}")
        await _safe_delete_message(bot, chat_id, waiting_msg)


async def _safe_delete_message(bot, chat_id, waiting_msg):
    """Безопасное удаление сообщения с логированием."""
    if waiting_msg:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=waiting_msg.message_id)
        except Exception as e:
            logger.debug(f"Не удалось удалить сообщение прогресса: {e}")