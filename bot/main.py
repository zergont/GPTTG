"""Точка входа приложения."""
import asyncio
import os
import atexit
import signal
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings, VERSION
from bot.middlewares import UserMiddleware, ErrorMiddleware
from bot import router
from bot.utils.log import logger
from bot.utils.http_client import close_session
from bot.utils.reminders import start_reminders_scheduler, start_self_calls_scheduler

# Путь к lock-файлу для single-instance
LOCK_PATH = Path(__file__).parent.parent / "gpttg-bot.lock"
_LOCK_PID: Optional[int] = None

# Режим разрешения нескольких экземпляров (для разработки / отладки)
ALLOW_MULTI = os.getenv("GPTTG_ALLOW_MULTI", "0") == "1"


def _pid_running(pid: int) -> bool:
    """Проверяет, существует ли процесс с данным PID."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Процесс существует, но нет прав послать сигнал
        return True
    except Exception:
        # В сомнительных случаях считаем, что процесс жив
        return True


def acquire_single_instance_lock() -> None:
    """Создаёт lock-файл и предотвращает запуск второго экземпляра."""
    global _LOCK_PID
    _LOCK_PID = os.getpid()

    if LOCK_PATH.exists():
        try:
            existing = int(LOCK_PATH.read_text(encoding="utf-8").strip())
        except Exception:
            existing = None

        if existing and _pid_running(existing):
            logger.error(f"Обнаружен запущенный экземпляр (PID {existing}). Завершаю работу.")
            raise SystemExit(1)
        else:
            # Считаем lock-файл протухшим
            try:
                LOCK_PATH.unlink(missing_ok=True)
            except Exception:
                pass

    try:
        LOCK_PATH.write_text(str(_LOCK_PID), encoding="utf-8")
        logger.debug(f"Создан lock-файл: {LOCK_PATH} (PID {_LOCK_PID})")
    except Exception as e:
        logger.error(f"Не удалось создать lock-файл {LOCK_PATH}: {e}")
        raise SystemExit(1)


def release_single_instance_lock() -> None:
    """Удаляет lock-файл, если он принадлежит текущему процессу."""
    try:
        if LOCK_PATH.exists():
            content = LOCK_PATH.read_text(encoding="utf-8").strip()
            if _LOCK_PID is None or content != str(_LOCK_PID):
                return
            LOCK_PATH.unlink(missing_ok=True)
            logger.debug("Lock-файл удалён")
    except Exception:
        # Не критично
        pass


def _signal_handler(signum, frame):
    # Чистим lock и выходим
    release_single_instance_lock()
    raise SystemExit(0)


async def main():
    """Основная функция запуска бота."""
    # Инициализация БД только один раз при старте
    from bot.utils.db import init_db, close_pool
    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # Регистрируем middleware
    dp.message.middleware(UserMiddleware())
    dp.message.middleware(ErrorMiddleware())
    dp.callback_query.middleware(ErrorMiddleware())

    # Регистрируем главный роутер (который уже включает все остальные роутеры)
    dp.include_router(router)  # Главный роутер из bot/__init__.py уже содержит admin_update

    logger.info(f"🚀 Запуск GPTTG бота версии {VERSION}")

    # Запускаем планировщики в фоне
    reminders_task = start_reminders_scheduler(bot)
    self_calls_task = start_self_calls_scheduler(bot)

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        # Останавливаем планировщики
        try:
            for t in (reminders_task, self_calls_task):
                stop_event = getattr(t, "_gpttg_stop_event", None)
                if stop_event is not None:
                    stop_event.set()
                t.cancel()
        except Exception:
            pass
        await close_session()
        await close_pool()
        await bot.session.close()


def run_bot():
    """Запуск бота с защитой от второго экземпляра."""
    # Для разрешённого мультизапуска просто предупреждаем
    if ALLOW_MULTI:
        logger.warning("⚠️  GPTTG_ALLOW_MULTI=1 — защита single-instance отключена (dev mode)")
        asyncio.run(main())
        return

    # Регистрируем очистку lock-файла
    atexit.register(release_single_instance_lock)
    try:
        # Устанавливаем обработчики сигналов для корректного завершения
        try:
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
        except Exception:
            # На некоторых платформах недоступно
            pass

        acquire_single_instance_lock()
        logger.info("🚀 Запуск бота...")
        asyncio.run(main())
    finally:
        release_single_instance_lock()


if __name__ == "__main__":
    run_bot()
