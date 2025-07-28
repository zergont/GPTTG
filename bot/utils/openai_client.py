"""УСТАРЕЛО: Этот файл оставлен для обратной совместимости.

Новая модульная структура находится в bot.utils.openai
"""

# Переэкспорт для обратной совместимости
from .openai import OpenAIClient

# Предупреждение об устаревании
import warnings
warnings.warn(
    "bot.utils.openai_client устарел. Используйте bot.utils.openai.OpenAIClient",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['OpenAIClient']