"""Вспомогательные модули (`log`, `db`, `openai_client`).
Экспортируем `logger`, чтобы в остальных частях приложения можно было писать
`from bot.utils import logger`.
"""
from .log import logger

__all__ = ["logger"]