"""Точка входа приложения."""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.middlewares import StartupMiddleware, UserMiddleware, ErrorMiddleware
from bot import router
from bot.utils.log import logger
from bot.utils.http_client import close_session
from bot.handlers.message_handler import router as message_router

async def main():
    """Основная функция запуска бота."""
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Регистрируем middleware (aiogram 3.x синтаксис)
    dp.message.middleware(StartupMiddleware())
    dp.message.middleware(UserMiddleware())  # Новый middleware для пользователей
    dp.message.middleware(ErrorMiddleware())
    dp.callback_query.middleware(StartupMiddleware())
    dp.callback_query.middleware(ErrorMiddleware())
    
    # Регистрируем роутеры
    dp.include_router(router)
    dp.include_router(message_router)
    
    logger.info("Starting bot…")
    
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await close_session()  # Закрываем HTTP сессию
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())


"""Голосовые сообщения → Whisper → текст → модель."""
from aiogram import Router
from aiogram.types import Message
import asyncio
from bot.config import settings
from bot.utils.openai_client import OpenAIClient
from bot.utils.http_client import download_file
from bot.utils.log import logger
from bot.utils.progress import show_progress_indicator
import io
import openai
import aiohttp

router = Router()

@router.message(lambda m: m.voice)
async def handle_voice(msg: Message):
    v = msg.voice
    if v.file_size > settings.max_file_mb * 1024 * 1024:
        await msg.reply(f"Файл слишком большой (>{settings.max_file_mb} МБ)")
        return

    file = await msg.bot.get_file(v.file_id)
    url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"

    # Отправляем первоначальное сообщение
    status_msg = await msg.answer("🎤 Обрабатываю голосовое сообщение...")
    
    # Запускаем индикатор прогресса в фоновом режиме
    progress_task = asyncio.create_task(show_progress_indicator(msg.bot, msg.chat.id))

    try:
        # Используем оптимизированный HTTP клиент
        data = await download_file(url)
        
        audio_file = io.BytesIO(data)
        audio_file.name = "voice.ogg"

        # Расшифровываем через Whisper
        text = await OpenAIClient.whisper(audio_file, msg.chat.id, msg.from_user.id)
        
        if not text.strip():
            progress_task.cancel()
            await status_msg.edit_text("❌ Не удалось распознать речь в голосовом сообщении")
            return

        # Отменяем индикатор и обновляем статус
        progress_task.cancel()
        await status_msg.edit_text(f"🗣 Вы сказали: {text}")

        # Запускаем новый индикатор для ответа модели
        progress_task = asyncio.create_task(show_progress_indicator(msg.bot, msg.chat.id))
        
        # Получаем ответ от модели
        content = [{"type": "message", "role": "user", "content": text}]
        response_text = await OpenAIClient.responses_request(msg.chat.id, content)
        
        # Отменяем индикатор и отправляем ответ
        progress_task.cancel()
        await msg.answer(response_text)

    except aiohttp.ClientError as e:
        progress_task.cancel()
        logger.error(f"Ошибка сети при загрузке голосового файла: {e}")
        await status_msg.edit_text("❌ Ошибка загрузки голосового файла. Попробуйте позже.")
    except openai.APITimeoutError:
        progress_task.cancel()
        await status_msg.edit_text("⏳ Время ожидания ответа от OpenAI истекло. Попробуйте ещё раз позже.")
    except Exception as e:
        progress_task.cancel()
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка: {str(e)[:100]}...")
logger.info("Bot shutdown complete")
