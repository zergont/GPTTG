"""HTTP клиент для загрузки файлов из Telegram и сетевых источников."""
import aiohttp
from bot.utils.log import logger

_session: aiohttp.ClientSession | None = None

def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total= get_total_timeout())
        _session = aiohttp.ClientSession(timeout=timeout)
    return _session

def get_total_timeout() -> float:
    # Привязываем HTTP-таймаут к OpenAI таймауту с буфером
    from bot.config import settings
    try:
        return float(getattr(settings, "openai_timeout_seconds", 180)) + 30.0
    except Exception:
        return 210.0

async def download_file(url: str) -> bytes:
    """Скачивает файл по URL и возвращает содержимое в виде bytes.
    Использует общую aiohttp-сессию с увеличенным таймаутом.
    """
    session = get_session()
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                msg = f"Ошибка загрузки файла {url}: {resp.status} {text[:200]}"
                logger.error(msg)
                raise aiohttp.ClientResponseError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    message=msg,
                    headers=resp.headers,
                )
            return await resp.read()
    except Exception as e:
        logger.error(f"download_file: {e}")
        raise

async def close_session():
    global _session
    if _session and not _session.closed:
        try:
            await _session.close()
            _session = None
        except Exception as e:
            logger.debug(f"Ошибка закрытия HTTP-сессии: {e}")