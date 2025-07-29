"""Управление моделями OpenAI."""
from typing import Any, Dict, List
from bot.utils.db import get_conn
from bot.utils.log import logger
from .base import client, RATE_LIMIT


class ModelsManager:
    """Управление моделями OpenAI."""
    
    # Простой список vision-моделей, поддерживающих Responses API
    VISION_MODELS = {
        'gpt-4o-mini',        # Базовая модель
        'gpt-4o',             # Основная модель
        'gpt-4-0125-preview', # Preview модель
        'gpt-4-1106-preview', # Preview модель
    }
    
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

    @staticmethod
    async def get_available_models() -> List[Dict[str, Any]]:
        """Получает список доступных vision-моделей."""
        try:
            async with RATE_LIMIT:
                models_response = await client.models.list()
                chat_models = []
                
                for model in models_response.data:
                    model_id = model.id
                    
                    # Показываем только наши vision-модели
                    if model_id in ModelsManager.VISION_MODELS:
                        chat_models.append({
                            'id': model_id,
                            'name': model_id,
                            'created': getattr(model, 'created', 0)
                        })
                
                # Добавляем базовые модели, если их нет в списке API
                existing_ids = {m['id'] for m in chat_models}
                for model_id in ['gpt-4o-mini', 'gpt-4o']:
                    if model_id not in existing_ids:
                        chat_models.append({
                            'id': model_id,
                            'name': model_id,
                            'created': 0
                        })
                
                chat_models.sort(key=lambda x: -x['created'])
                logger.info(f"Найдено {len(chat_models)} vision-моделей")
                return chat_models
                
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return [
                {'id': 'gpt-4o-mini', 'name': 'gpt-4o-mini', 'created': 0},
                {'id': 'gpt-4o', 'name': 'gpt-4o', 'created': 0},
            ]