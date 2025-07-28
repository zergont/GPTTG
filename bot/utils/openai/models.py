"""Управление моделями OpenAI."""
from typing import Any, Dict, List
from bot.utils.db import get_conn
from bot.utils.log import logger
from .base import client, RATE_LIMIT


class ModelsManager:
    """Управление моделями OpenAI."""
    
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

    @staticmethod
    async def get_available_models() -> List[Dict[str, Any]]:
        """Получает список доступных моделей от OpenAI."""
        try:
            async with RATE_LIMIT:
                models_response = await client.models.list()
                chat_models = []
                for model in models_response.data:
                    model_id = model.id
                    if any(prefix in model_id.lower() for prefix in ['gpt-4', 'gpt-3.5']):
                        chat_models.append({
                            'id': model_id,
                            'name': model_id,
                            'created': getattr(model, 'created', 0)
                        })
                chat_models.sort(key=lambda x: x['created'], reverse=True)
                return chat_models
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return [
                {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini (default)', 'created': 0},
                {'id': 'gpt-4o', 'name': 'GPT-4o', 'created': 0},
                {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'created': 0},
                {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'created': 0},
            ]