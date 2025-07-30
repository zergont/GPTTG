"""Точка входа приложения."""
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings, VERSION
from bot.middlewares import StartupMiddleware, UserMiddleware, ErrorMiddleware
from bot import router
from bot.utils.log import logger
from bot.utils.http_client import close_session


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
    # Инициализация БД только один раз при старте
    from bot.utils.db import init_db
    await init_db()

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

    # Регистрируем главный роутер (который уже включает все остальные роутеры)
    dp.include_router(router)  # Главный роутер из bot/__init__.py уже содержит admin_update

    logger.info(f"🚀 Запуск GPTTG бота версии {VERSION}")

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
