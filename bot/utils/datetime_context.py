"""Утилиты для обработки времени и контекста сообщений."""
from datetime import datetime
import pytz


def get_current_datetime_info() -> str:
    """Возвращает текущую дату и время в удобном для ИИ формате."""
    # Используем московское время
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    
    return (
        f"Текущая дата и время: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"(московское время, {now.strftime('%A, %d %B %Y')})"
    )


def enhance_user_content_with_datetime(user_text: str) -> str:
    """Добавляет временной контекст к сообщению пользователя."""
    datetime_info = get_current_datetime_info()
    return f"{datetime_info}\n\nСообщение пользователя: {user_text}"


def enhance_content_dict_with_datetime(content_dict: dict) -> dict:
    """Добавляет временной контекст к словарю контента для OpenAI API."""
    if content_dict.get("type") == "message" and content_dict.get("role") == "user":
        # Если контент - строка
        if isinstance(content_dict.get("content"), str):
            original_content = content_dict["content"]
            content_dict["content"] = enhance_user_content_with_datetime(original_content)
        
        # Если контент - список (например, для мультимодальных запросов)
        elif isinstance(content_dict.get("content"), list):
            datetime_info = get_current_datetime_info()
            
            # Находим первый текстовый элемент и добавляем к нему время
            for item in content_dict["content"]:
                if isinstance(item, dict) and item.get("type") in ["input_text", "text"]:
                    original_text = item.get("text", "")
                    item["text"] = f"{datetime_info}\n\n{original_text}"
                    break
            else:
                # Если текстового элемента нет, добавляем его в начало
                content_dict["content"].insert(0, {
                    "type": "input_text",
                    "text": datetime_info
                })
    
    return content_dict