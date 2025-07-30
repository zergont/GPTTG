"""Кэшированное управление моделями."""
import asyncio
from typing import List, Dict, Any
import time
from bot.utils.db import get_conn
from bot.utils.log import logger
from .base import client, RATE_LIMIT


class ModelsManager:
    """Управление моделями OpenAI."""

    _models_cache: List[Dict[str, Any]] = []
    _cache_timestamp: float = 0
    _cache_ttl: int = 3600  # 1 час

    @classmethod
    async def get_available_models(cls) -> List[Dict[str, Any]]:
        """Получает список доступных моделей с кэшированием."""
        now = time.time()

        if now - cls._cache_timestamp < cls._cache_ttl and cls._models_cache:
            return cls._models_cache

        # Обновляем кэш
        models = await cls._fetch_models_from_api()
        cls._models_cache = models
        cls._cache_timestamp = now

        return models

    @staticmethod
    async def get_current_model() -> str:
        """Получает текущую активную модель из базы данных."""        
        async with get_conn() as db:
            cur = await db.execute(
                "SELECT value FROM bot_settings WHERE key = 'current_model'"
            )
            row = await cur.fetchone()
            return row[0] if row else "gpt-4o-mini"

    @staticmethod
    async def set_current_model(model: str) -> None:
        """Устанавливает текущую модель в базе данных."""        
        async with get_conn() as db:
            await db.execute(
                "REPLACE INTO bot_settings (key, value) VALUES ('current_model', ?)",
                (model,)
            )
            await db.commit()
            logger.info(f"Модель изменена на {model}")

    @classmethod
    async def _fetch_models_from_api(cls) -> List[Dict[str, Any]]:
        """Получает список моделей из API OpenAI."""
        try:
            async with RATE_LIMIT:
                models_response = await client.models.list()
                chat_models = []

                for model in models_response.data:
                    model_id = model.id
                    chat_models.append({
                        'id': model_id,
                        'name': model_id,
                        'created': getattr(model, 'created', 0)
                    })

                chat_models.sort(key=lambda x: -x['created'])
                logger.info(f"Найдено {len(chat_models)} моделей")
                return chat_models

        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            # Возвращаем базовые модели по умолчанию
            return [
                {'id': 'gpt-4o-mini', 'name': 'gpt-4o-mini', 'created': 0},
                {'id': 'gpt-4o', 'name': 'gpt-4o', 'created': 0},
            ]