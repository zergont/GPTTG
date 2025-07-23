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
import aiocron

from bot.config import settings, VERSION
from bot.middlewares import StartupMiddleware, UserMiddleware, ErrorMiddleware
from bot import router
from bot.utils.log import logger
from bot.utils.http_client import close_session

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

def setup_cron(bot):
    try:
        aiocron.crontab('0 10 * * *', func=lambda: asyncio.create_task(daily_version_check(bot)))
        logger.info("✅ Планировщик автообновления настроен (10:00 UTC)")
    except Exception as e:
        logger.error(f"❌ Ошибка настройки планировщика: {e}")

async def process_update_yes(callback: CallbackQuery):
    status_msg = await callback.message.answer("⏳ Обновление запущено… Ожидайте примерно 1 минуту.")
    try:
        # Показываем таймер ожидания (обновляем сообщение каждую 10 сек)
        for i in range(3):  # Уменьшили количество итераций
            await asyncio.sleep(5)  # Уменьшили время ожидания
            try:
                await status_msg.edit_text(f"⏳ Обновление идёт… Осталось ~{15 - (i+1)*5} сек.")
            except Exception:
                break  # Если сообщение уже не доступно, выходим
        
        # Закрываем HTTP сессию перед запуском скрипта обновления
        await close_session()
        
        # Создаем полностью независимый скрипт обновления
        independent_updater = """#!/bin/bash
# Независимый скрипт обновления - не связан с systemd сервисом
set -e

# Переходим в нужную директорию
cd /root/GPTTG

# Делаем обновление файлов Git
echo "📥 Загрузка обновлений..."
git fetch origin
git reset --hard origin/beta

# Запускаем основной скрипт обновления
chmod +x ./update_bot.sh
echo "🚀 Запуск основного скрипта обновления..."
exec ./update_bot.sh
"""
        
        # Записываем независимый скрипт во временный файл
        with open("/tmp/independent_update.sh", "w") as f:
            f.write(independent_updater)
        
        # Делаем скрипт исполняемым и запускаем его в полностью отдельном процессе
        commands = [
            "chmod +x /tmp/independent_update.sh",
            "cd /root/GPTTG",
            "setsid /tmp/independent_update.sh > /tmp/gpttg_update.log 2>&1 &"  # setsid создает новую сессию
        ]
        
        result = subprocess.run([
            "/bin/bash", "-c", " && ".join(commands)
        ], capture_output=True, text=True, timeout=15)  # Короткий timeout только для запуска
        
        # Отправляем результат запуска (не ожидаем завершения обновления)
        if result.returncode == 0:
            success_msg = (
                "✅ Автообновление запущено в независимом процессе!\n\n"
                "🔄 Бот будет перезапущен автоматически через ~30 секунд.\n"
                "📋 Проверьте статус командой /status через 2 минуты.\n"
                "📄 Логи: tail -f /tmp/gpttg_update.log"
            )
            try:
                await callback.message.answer(success_msg)
            except Exception:
                pass
        else:
            # Отправляем подробную диагностику только при ошибке запуска
            error_info = f"❌ Ошибка запуска обновления (код: {result.returncode})\n\n"
            if result.stdout:
                error_info += f"📤 STDOUT:\n{result.stdout[-800:]}\n\n"
            if result.stderr:
                error_info += f"❌ STDERR:\n{result.stderr[-800:]}\n\n"
            
            try:
                await callback.message.answer(error_info[:4000])  # Telegram лимит
            except Exception:
                # Если не удается отправить, попробуем короткое сообщение
                try:
                    await callback.message.answer(f"❌ Обновление неудачно. Код ошибки: {result.returncode}")
                except Exception:
                    pass
        return  # После запуска скрипта не отправлять сообщений!
    except subprocess.TimeoutExpired:
        try:
            await callback.message.answer("⏰ Запуск обновления превысил лимит времени (15 сек). Попробуйте /checkupdate.")
        except Exception:
            pass
    except Exception as e:
        try:
            await callback.message.answer(f"❌ Ошибка запуска обновления: {e}")
        except Exception:
            # Игнорируем ошибки отправки, так как бот может уже перезапускаться
            pass

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

def ensure_single_instance_safe():
    """Безопасная проверка единственного экземпляра с fallback."""
    try:
        from bot.utils.single_instance import ensure_single_instance
        return ensure_single_instance("gpttg-bot.lock")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось настроить блокировку экземпляра: {e}")
        logger.info("🔄 Продолжаю запуск без блокировки...")
        # Возвращаем dummy context manager
        from contextlib import nullcontext
        return nullcontext()

async def main():
    """Основная функция запуска бота."""
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Регистрируем middleware
    dp.message.middleware(StartupMiddleware())
    dp.message.middleware(UserMiddleware())
    dp.message.middleware(ErrorMiddleware())
    dp.callback_query.middleware(StartupMiddleware())
    dp.callback_query.middleware(ErrorMiddleware())
    
    # Регистрируем роутеры
    dp.include_router(router)  # Главный роутер из bot/__init__.py
    dp.include_router(update_router)
    
    logger.info("Starting bot…")
    await notify_update(bot)
    setup_cron(bot)
    
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await close_session()
        await bot.session.close()

def run_bot():
    """Запуск бота с опциональной проверкой единственного экземпляра."""
    # Пытаемся настроить блокировку, но не падаем при ошибке
    with ensure_single_instance_safe():
        logger.info("🚀 Запуск бота...")
        asyncio.run(main())

if __name__ == "__main__":
    run_bot()

# Экспортируем функции для использования в других модулях
__all__ = [
    "check_github_version",
    "send_update_prompt", 
    "VERSION"
]
