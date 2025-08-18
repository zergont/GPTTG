"""Базовая настройка логирования с ротацией файлов."""
import logging
import sys
import os
import glob
from logging.handlers import RotatingFileHandler
from bot.config import settings


def _purge_old_logs() -> None:
    """Удаляет старые лог-файлы при старте.

    Удаляются все файлы в каталоге logs, соответствующие шаблонам:
    - *.log
    - *.log.* (файлы ротации)
    Выполняется до инициализации обработчиков логирования.
    """
    try:
        os.makedirs("logs", exist_ok=True)
        removed = 0
        for pattern in ("*.log", "*.log.*"):
            for path in glob.glob(os.path.join("logs", pattern)):
                try:
                    os.remove(path)
                    removed += 1
                except FileNotFoundError:
                    continue
                except PermissionError:
                    # На Windows файл мог быть занят — просто пропускаем
                    continue
                except Exception:
                    continue
        if removed:
            print(f"🧹 Очищено лог‑файлов: {removed}")
    except Exception as e:
        # Не блокируем запуск бота из‑за ошибок очистки
        print(f"[log] Не удалось очистить старые логи: {e}")


# Очищаем логи до настройки обработчиков
_purge_old_logs()

# Настраиваем обработчики логов
log_handlers = [logging.StreamHandler(sys.stdout)]

# Добавляем файловый обработчик с ротацией, если включен debug режим
if getattr(settings, "debug_mode", False):
    os.makedirs("logs", exist_ok=True)

    # Размер в байтах (MAX_LOG_MB * 1024 * 1024)
    max_bytes = getattr(settings, "max_log_mb", 5) * 1024 * 1024

    # RotatingFileHandler с ограничением размера и количества backup файлов
    rotating_handler = RotatingFileHandler(
        filename="logs/bot.log",
        maxBytes=max_bytes,
        backupCount=3,  # Храним 3 резервные копии
        encoding="utf-8"
    )

    log_handlers.append(rotating_handler)
    print(f"📝 Логи будут записываться в файл с ограничением {max_bytes // (1024*1024)} МБ")

# Настраиваем базовое логирование
logging.basicConfig(
    level=logging.DEBUG if getattr(settings, "debug_mode", False) else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers,
)

logger = logging.getLogger("bot")