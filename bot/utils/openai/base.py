"""Базовые компоненты для работы с OpenAI API."""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict

from openai import AsyncOpenAI
from bot.config import settings

# Общий клиент OpenAI с настройками
client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout_seconds,  # Таймаут из настроек (по умолчанию 180 сек)
    max_retries=settings.openai_max_retries  # Количество ретраев из настроек (по умолчанию 0)
)

# ——— Ограничение параллелизма ——————————————————————————————
# Глобальный лимит параллельных запросов к OpenAI (на весь процесс)
_GLOBAL_LIMIT = asyncio.Semaphore(getattr(settings, "openai_global_concurrency", 4))

# Пер‑чату лимит: не более 1 запроса к OpenAI одновременно на chat_id
_chat_limits: Dict[int, asyncio.Semaphore] = {}
_chat_limits_lock = asyncio.Lock()


async def _get_chat_limit(chat_id: int) -> asyncio.Semaphore:
    async with _chat_limits_lock:
        sem = _chat_limits.get(chat_id)
        if sem is None:
            sem = asyncio.Semaphore(1)
            _chat_limits[chat_id] = sem
        return sem


@asynccontextmanager
async def oai_limiter(chat_id: int | None):
    """Контекстный менеджер: резервирует глобальный слот и слот чата.
    Если chat_id не указан, используется только глобальный слот.
    """
    if chat_id is None:
        async with _GLOBAL_LIMIT:
            yield
        return

    chat_sem = await _get_chat_limit(chat_id)
    async with _GLOBAL_LIMIT:
        async with chat_sem:
            yield