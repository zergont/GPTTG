"""Модели и текущая модель для OpenAI."""
from __future__ import annotations
from typing import List, Dict, Tuple
from bot.utils.db import get_conn
from bot.config import settings


class ModelsManager:
    """Управление доступными моделями и текущим выбором."""

    DEFAULT_MODEL = "gpt-4o-mini"
    SETTINGS_KEY = "current_model"

    # Цены за 1k токенов (USD). Основано на публичном прайсе OpenAI (обновлено 2025‑08‑12).
    # Для некоторых моделей есть скидка на закешированные входные токены (cached_input).
    # Формат: model -> { input, cached_input (опц.), output }
    PRICING_USD_PER_1K: Dict[str, Dict[str, float]] = {
        # GPT‑4o линейка (примерные значения)
        "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
        "gpt-4o": {"input": 0.00500, "output": 0.01500},
        # GPT‑5 линейка (актуально на 2025‑08‑12)
        "gpt-5": {"input": 0.00125, "cached_input": 0.000125, "output": 0.01000},
        "gpt-5-mini": {"input": 0.00025, "cached_input": 0.000025, "output": 0.00200},
        "gpt-5-nano": {"input": 0.00005, "cached_input": 0.000005, "output": 0.00040},
    }

    @staticmethod
    async def get_available_models() -> List[Dict[str, str]]:
        """Возвращает список доступных моделей с id и описанием.
        Можно расширить логикой запроса к OpenAI.
        """
        return [
            {"id": "gpt-4o-mini", "description": "Оптимальная скорость/цена (мультимодальная)"},
            {"id": "gpt-4o", "description": "Качество и мультимодальность"},
            {"id": "gpt-5", "description": "Флагман, выше качество, дороже"},
            {"id": "gpt-5-mini", "description": "Ускоренная и бюджетная версия"},
            {"id": "gpt-5-nano", "description": "Максимально быстрая и дешёвая"},
        ]

    @staticmethod
    async def get_current_model() -> str:
        async with get_conn() as db:
            cur = await db.execute(
                "SELECT value FROM bot_settings WHERE key = ? LIMIT 1",
                (ModelsManager.SETTINGS_KEY,),
            )
            row = await cur.fetchone()
            if not row or not row[0]:
                return ModelsManager.DEFAULT_MODEL
            return row[0]

    @staticmethod
    async def set_current_model(model_id: str) -> None:
        async with get_conn() as db:
            # Простейшая валидация: только из списка доступных
            available = {m["id"] for m in await ModelsManager.get_available_models()}
            if model_id not in available:
                model_id = ModelsManager.DEFAULT_MODEL
            # UPSERT в bot_settings
            await db.execute(
                "INSERT OR REPLACE INTO bot_settings(key, value) VALUES (?, ?)",
                (ModelsManager.SETTINGS_KEY, model_id),
            )
            await db.commit()

    @staticmethod
    def get_model_pricing(model: str) -> Tuple[float, float]:
        """DEPRECATED: оставлено для обратной совместимости.
        Возвращает (input_price_per_1k, output_price_per_1k).
        """
        p = ModelsManager.PRICING_USD_PER_1K.get(model)
        if p:
            return p.get("input", 0.0), p.get("output", 0.0)
        # Fallback на глобальную цену, если задана, иначе 0
        fallback = getattr(settings, "openai_price_per_1k_tokens", 0.0) or 0.0
        return fallback, fallback

    @staticmethod
    def get_model_prices(model: str) -> Dict[str, float]:
        """Возвращает словарь цен {input, output, cached_input?} за 1k токенов для модели.
        Если модель не найдена — возвращает fallback на глобальную цену для input/output, без cached_input.
        """
        p = ModelsManager.PRICING_USD_PER_1K.get(model)
        if p:
            return p
        fallback = getattr(settings, "openai_price_per_1k_tokens", 0.0) or 0.0
        return {"input": fallback, "output": fallback}