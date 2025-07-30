"""Оптимизированный HTTP клиент для загрузки файлов."""
import aiohttp
from bot.config import settings

# Создаем единый HTTP клиент для всего приложения
_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    """Получить HTTP сессию (singleton)."""
    global _session
    if _session is None or _session.closed:
        # Исправлено: используем секунды вместо мегабайт для таймаута
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        _session = aiohttp.ClientSession(
            timeout=timeout,
            connector=aiohttp.TCPConnector(
                limit=10,           # Уменьшено с 20
                limit_per_host=5,   # Уменьшено с 10
                ttl_dns_cache=300,  # Кэш DNS на 5 минут
                use_dns_cache=True
            )
        )
    return _session

async def close_session():
    """Закрыть HTTP сессию."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

async def download_file(url: str, max_size: int = None) -> bytes:
    """Загрузить файл по URL с ограничением размера."""
    session = await get_session()
    max_size = max_size or (settings.max_file_mb * 1024 * 1024)
    
    async with session.get(url) as resp:
        if resp.status != 200:
            raise aiohttp.ClientError(f"HTTP {resp.status}")
        
        # Проверяем размер файла из заголовков
        content_length = resp.headers.get('content-length')
        if content_length and int(content_length) > max_size:
            raise aiohttp.ClientError(f"Файл слишком большой: {content_length} байт")
        
        # Чтение с ограничением размера
        data = b""
        async for chunk in resp.content.iter_chunked(8192):
            data += chunk
            if len(data) > max_size:
                raise aiohttp.ClientError(f"Файл превышает лимит: {max_size} байт")
        
        return data