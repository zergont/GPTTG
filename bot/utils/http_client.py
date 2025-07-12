"""Общий HTTP клиент для загрузки файлов."""
import aiohttp
from bot.config import settings

# Создаем единый HTTP клиент для всего приложения
_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    """Получить HTTP сессию (singleton)."""
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=settings.max_file_mb, connect=5)
        _session = aiohttp.ClientSession(
            timeout=timeout,
            connector=aiohttp.TCPConnector(limit=20, limit_per_host=10)
        )
    return _session

async def close_session():
    """Закрыть HTTP сессию."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

async def download_file(url: str) -> bytes:
    """Загрузить файл по URL."""
    session = await get_session()
    async with session.get(url) as resp:
        if resp.status != 200:
            raise aiohttp.ClientError(f"HTTP {resp.status}")
        return await resp.read()