"""Генерация изображений через DALL-E."""
from bot.utils.log import logger
from .base import client, RATE_LIMIT


class DalleManager:
    """Управление генерацией изображений через DALL-E."""
    
    @staticmethod
    async def generate_image(prompt: str, size: str, chat_id: int, user_id: int) -> str | None:
        """Генерирует изображение через OpenAI DALL·E и возвращает URL."""
        async with RATE_LIMIT:
            try:
                # Используем официальный AsyncOpenAI для генерации изображения
                response = await client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size=size,
                    user=str(user_id)
                )
                # DALL·E 3 возвращает список изображений
                if response and hasattr(response, 'data') and response.data:
                    return response.data[0].url
                logger.error(f"DALL·E не вернул изображение: {response}")
                return None
            except Exception as e:
                logger.error(f"Ошибка генерации изображения DALL·E: {e}")
                return None