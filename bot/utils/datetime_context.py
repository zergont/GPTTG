"""Утилиты для обработки времени и контекста сообщений."""
from datetime import datetime, timezone
import pytz
from typing import Optional
from .db import get_conn, get_user_timezone


def _safe_get_tz(tz_name: Optional[str]) -> pytz.timezone:
    try:
        return pytz.timezone(tz_name or 'Europe/Moscow')
    except Exception:
        return pytz.timezone('Europe/Moscow')


async def get_current_datetime_info(user_id: Optional[int] = None) -> str:
    """Возвращает текущую дату и время в формате ассистента для заданного пользователя (его часовой пояс)."""
    if user_id:
        tz_name = await get_user_timezone(user_id)
    else:
        tz_name = 'Europe/Moscow'
    user_tz = _safe_get_tz(tz_name)
    now = datetime.now(user_tz)
    return (
        f"Текущая дата и время: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({tz_name}, {now.strftime('%A, %d %B %Y')})"
    )


async def enhance_user_content_with_datetime(user_text: str, user_id: Optional[int]) -> str:
    """Добавляет временной контекст с учётом часового пояса пользователя."""
    datetime_info = await get_current_datetime_info(user_id)
    return f"{datetime_info}\n\nСообщение пользователя: {user_text}"


async def enhance_content_dict_with_datetime(content_dict: dict, user_id: Optional[int]) -> dict:
    """Добавляет временной контекст к словарю контента для OpenAI API (с TZ пользователя)."""
    if content_dict.get("type") == "message" and content_dict.get("role") == "user":
        if isinstance(content_dict.get("content"), str):
            original_content = content_dict["content"]
            content_dict["content"] = await enhance_user_content_with_datetime(original_content, user_id)
        elif isinstance(content_dict.get("content"), list):
            datetime_info = await get_current_datetime_info(user_id)
            for item in content_dict["content"]:
                if isinstance(item, dict) and item.get("type") in ["input_text", "text"]:
                    original_text = item.get("text", "")
                    item["text"] = f"{datetime_info}\n\n{original_text}"
                    break
            else:
                content_dict["content"].insert(0, {
                    "type": "input_text",
                    "text": await get_current_datetime_info(user_id)
                })
    return content_dict


def utc_to_user_local(utc_str: str, user_tz_name: Optional[str]) -> str:
    """Преобразует строку UTC '%Y-%m-%d %H:%M:%S' в локальное время пользователя и форматирует."""
    try:
        dt = datetime.strptime(utc_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        tz = _safe_get_tz(user_tz_name or 'Europe/Moscow')
        local_dt = dt.astimezone(tz)
        return local_dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return utc_str