"""Точка входа приложения."""
import asyncio
import os

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
from bot.utils.updater import SimpleUpdater


async def send_update_prompt(bot, admin_id, current_version, remote_version):
    """Отправляет уведомление о доступном обновлении."""
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
    """Ежедневная проверка версии."""
    remote_version = await SimpleUpdater.check_remote_version()
    if remote_version and remote_version != VERSION:
        await send_update_prompt(bot, settings.admin_id, VERSION, remote_version)


def setup_cron(bot):
    """Настраивает планировщик автопроверки обновлений."""
    try:
        aiocron.crontab('0 10 * * *', func=lambda: asyncio.create_task(daily_version_check(bot)))
        logger.info("✅ Планировщик автообновления настроен (10:00 UTC)")
    except Exception as e:
        logger.error(f"❌ Ошибка настройки планировщика: {e}")


async def process_update_yes(callback: CallbackQuery):
    """Обрабатывает подтверждение обновления."""
    await callback.answer()
    
    status_msg = await callback.message.answer("⏳ Запуск обновления...")
    
    try:
        # Закрываем HTTP сессии перед обновлением
        await close_session()
        
        # Запускаем простое обновление
        success, message = await SimpleUpdater.start_update()
        
        if success:
            await status_msg.edit_text(
                f"✅ {message}\n\n"
                "🔄 Бот перезапустится автоматически\n"
                "📊 Проверьте статус через /status через минуту"
            )
        else:
            await status_msg.edit_text(f"❌ {message}")
            
    except Exception as e:
        logger.error(f"Ошибка процесса обновления: {e}")
        try:
            await status_msg.edit_text(f"❌ Ошибка обновления: {str(e)[:100]}")
        except Exception:
            pass


async def process_update_no(callback: CallbackQuery):
    """Обрабатывает отмену обновления."""
    await callback.answer()
    await callback.message.edit_text("Обновление отменено.")


# Регистрируем callback handlers для обновления
from aiogram import Router
update_router = Router()
update_router.callback_query.register(process_update_yes, F.data == "update_yes")
update_router.callback_query.register(process_update_no, F.data == "update_no")


async def notify_update(bot: Bot):
    """Уведомляет об успешном обновлении."""
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
    with ensure_single_instance_safe():
        logger.info("🚀 Запуск бота...")
        asyncio.run(main())


if __name__ == "__main__":
    run_bot()


# Экспортируем функции для использования в других модулях
__all__ = [
    "send_update_prompt", 
    "VERSION"
]
