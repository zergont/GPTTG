"""Базовые компоненты для работы с OpenAI API."""
import asyncio
from openai import AsyncOpenAI
from bot.config import settings

# Общий клиент OpenAI с настройками
client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    timeout=60,  # Увеличен с 30 до 60 секунд для работы с файлами
    max_retries=2
)

# Общий семафор для ограничения количества одновременных запросов
RATE_LIMIT = asyncio.Semaphore(4)