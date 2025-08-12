"""Генерация изображений через DALL-E."""
from bot.utils.log import logger
from .base import client, oai_limiter
from bot.utils.db import get_conn
from bot.config import settings


class DalleManager:
    """Управление генерацией изображений через DALL-E."""
    
    @staticmethod
    async def generate_image(prompt: str, size: str, chat_id: int, user_id: int) -> str | None:
        """Генерирует изображение через OpenAI DALL·E и возвращает URL."""
        async with oai_limiter(chat_id):
            try:
                response = await client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size=size,
                    user=str(user_id)
                )
                if response and hasattr(response, 'data') and response.data:
                    url = response.data[0].url
                    # Учёт расходов DALL·E: фиксированная цена из настроек
                    async with get_conn() as db:
                        await db.execute(
                            "INSERT INTO usage(chat_id, user_id, tokens, cost, model) VALUES (?, ?, ?, ?, ?)",
                            (chat_id, user_id, 0, settings.dalle_price, "dall-e-3")
                        )
                        await db.commit()
                    return url
                logger.error(f"DALL·E не вернул изображение: {response}")
                return None
            except Exception as e:
                logger.error(f"Ошибка генерации изображения DALL·E: {e}")
                return None