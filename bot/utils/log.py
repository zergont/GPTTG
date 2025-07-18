"""Базовая настройка логирования (stdout, уровень INFO)."""
import logging
import sys
import os
from bot.config import settings

log_handlers = [logging.StreamHandler(sys.stdout)]
if getattr(settings, "debug_mode", False):
    os.makedirs("logs", exist_ok=True)
    log_handlers.append(logging.FileHandler("logs/bot.log", encoding="utf-8"))

logging.basicConfig(
    level=logging.DEBUG if getattr(settings, "debug_mode", False) else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers,
)

logger = logging.getLogger("bot")