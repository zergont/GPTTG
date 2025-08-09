"""Базовая настройка логирования с ротацией файлов."""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from bot.config import settings

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