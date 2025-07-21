"""Точка входа приложения."""
import asyncio
import os
import aiohttp
import subprocess
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.config import settings, VERSION
from bot.middlewares import StartupMiddleware, UserMiddleware, ErrorMiddleware
from bot import router
from bot.utils.log import logger
from bot.utils.http_client import close_session
from bot.handlers.message_handler import router as message_router

# Проверка и установка aiocron
try:
    import aiocron
except ImportError:
    print("Устанавливается пакет aiocron...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiocron"])
    import aiocron

async def check_github_version():
    url = "https://raw.githubusercontent.com/zergont/GPTTG/beta/pyproject.toml"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
    for line in text.splitlines():
        if line.strip().startswith("version"):
            remote_version = line.split("=")[1].strip().strip('"')
            break
    else:
        remote_version = None
    return remote_version

async def send_update_prompt(bot, admin_id, current_version, remote_version):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Обновить", callback_data="update_yes"),
                InlineKeyboardButton(text="Отмена", callback_data="update_no"),
            ]
        ]
    )
    await bot.send_message(
        admin_id,
        f"⚡️ Доступна новая версия: {remote_version}\n"
        f"Текущая версия: {current_version}\n"
        "Обновить сейчас?",
        reply_markup=keyboard
    )

async def daily_version_check(bot):
    remote_version = await check_github_version()
    if remote_version and remote_version != VERSION:
        await send_update_prompt(bot, settings.admin_id, VERSION, remote_version)

# aiocron: запускать каждый день в 10:00 UTC (13:00 МСК)
def setup_cron(bot):
    aiocron.crontab('0 10 * * *', func=lambda: asyncio.create_task(daily_version_check(bot)))

# CallbackQuery handlers
async def process_update_yes(callback: CallbackQuery):
    await callback.message.answer("⏳ Обновление запущено…")
    try:
        # Принудительный git pull (discard local changes)
        result = subprocess.run([
            "/bin/bash", "-c",
            "git fetch origin && git reset --hard origin/beta && ./update_bot.sh"
        ], capture_output=True, text=True)
        if result.returncode == 0:
            await callback.message.answer(f"✅ Обновление завершено!\n{result.stdout[-1000:]}")
        else:
            await callback.message.answer(f"❌ Ошибка обновления:\n{result.stderr[-1000:]}")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка обновления: {e}")

async def process_update_no(callback: CallbackQuery):
    await callback.message.answer("Обновление отменено.")

# Регистрация callback handlers
from aiogram import Router
update_router = Router()
update_router.callback_query.register(process_update_yes, F.data == "update_yes")
update_router.callback_query.register(process_update_no, F.data == "update_no")

async def notify_update(bot: Bot):
    version_file = "last_version.txt"
    last_version = None
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            last_version = f.read().strip()
    if last_version != VERSION:
        await bot.send_message(
            settings.admin_id,
            f"✅ Бот обновлён до версии {VERSION}!"
        )
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(VERSION)

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
    dp.include_router(update_router)
    
    logger.info("Starting bot…")
    await notify_update(bot)  # уведомление об обновлении
    setup_cron(bot)
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
