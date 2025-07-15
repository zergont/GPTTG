"""Утилиты для отображения индикаторов прогресса."""

import asyncio
from bot.utils.log import logger

async def show_progress_indicator(bot, chat_id, max_time=120, interval=2):
    """
    Показывает индикатор загрузки для aiogram 3.x
    
    Args:
        bot: Экземпляр бота aiogram
        chat_id: ID чата для отправки сообщения
        max_time: Максимальное время ожидания в секундах
        interval: Интервал обновления индикатора в секундах
    """
    indicators = ["⏳", "🔄", "⌛", "🤔", "💭", "🧠"]
    waiting_msg = None
    
    try:
        # Сначала отправляем сообщение о начале обработки
        waiting_msg = await bot.send_message(
            chat_id=chat_id, 
            text="Обрабатываю ваш запрос... ⏳"
        )
        
        # Затем периодически обновляем его, чтобы показать прогресс
        max_cycles = max_time // interval
        for i in range(max_cycles):
            await asyncio.sleep(interval)
            current_indicator = indicators[i % len(indicators)]
            seconds = (i + 1) * interval
            
            # Обновляем сообщение разными индикаторами
            await bot.edit_message_text(
                text=f"Обрабатываю ваш запрос... {current_indicator}\n"
                     f"Прошло {seconds} сек. Пожалуйста, подождите.",
                chat_id=chat_id,
                message_id=waiting_msg.message_id
            )
    except asyncio.CancelledError:
        # Задача была отменена, значит ответ готов
        if waiting_msg:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=waiting_msg.message_id)
            except Exception:
                # Игнорируем ошибку, если сообщение уже удалено
                pass
    except Exception as e:
        logger.error(f"Ошибка в индикаторе прогресса: {e}")