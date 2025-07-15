"""Базовая настройка логирования (stdout, уровень INFO)."""
import logging
import sys
from bot.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("bot")

if getattr(settings, "debug_mode", False):
    logger.setLevel(logging.DEBUG)