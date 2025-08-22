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

# Потоковый обработчик (stdout) всегда включен
log_handlers = [logging.StreamHandler(sys.stdout)]

# Файловый обработчик с ротацией теперь используется и в проде,
# но с разными уровнями:
#  - DEBUG_MODE=1 → пишем всё (DEBUG)
#  - DEBUG_MODE=0 → пишем только ошибки (ERROR)
try:
    os.makedirs("logs", exist_ok=True)
    max_bytes = getattr(settings, "max_log_mb", 5) * 1024 * 1024
    rotating_handler = RotatingFileHandler(
        filename="logs/bot.log",
        maxBytes=max_bytes,
        backupCount=3,
        encoding="utf-8",
    )
    rotating_handler.setLevel(logging.DEBUG if getattr(settings, "debug_mode", False) else logging.ERROR)
    log_handlers.append(rotating_handler)
    print(
        f"📝 Логи пишутся в logs/bot.log (уровень: "
        f"{'DEBUG' if getattr(settings, 'debug_mode', False) else 'ERROR'}; "
        f"лимит {max_bytes // (1024*1024)} МБ)"
    )
except Exception as e:
    print(f"[log] Не удалось создать файловый обработчик: {e}")

# Уровень корневого логгера:
#  - DEBUG_MODE=1 → DEBUG (и stdout, и файл получают debug)
#  - DEBUG_MODE=0 → INFO (stdout INFO+, файл отфильтрует до ERROR)
logging.basicConfig(
    level=logging.DEBUG if getattr(settings, "debug_mode", False) else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers,
)

logger = logging.getLogger("bot")