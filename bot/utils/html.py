"""Утилиты для работы с HTML форматированием в Telegram."""
from typing import List
from aiogram.types import Message


def escape_html(text: str) -> str:
    """
    Экранирует спецсимволы для HTML в Telegram.
    
    Args:
        text: Исходный текст
        
    Returns:
        str: Экранированный текст
    """
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def split_long_html_message(text: str, max_length: int = 4096) -> List[str]:
    """
    Разбивает длинное HTML сообщение на части, сохраняя читаемость.
    
    Args:
        text: Исходный HTML текст
        max_length: Максимальная длина одного сообщения
        
    Returns:
        List[str]: Список частей сообщения
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(text):
        # Определяем границу следующего чанка
        end_pos = current_pos + max_length
        
        if end_pos >= len(text):
            # Последний кусок
            chunks.append(text[current_pos:])
            break
        
        # Ищем удобное место для разрыва (по переносу строки)
        safe_break = text.rfind('\n', current_pos, end_pos)
        if safe_break == -1 or safe_break == current_pos:
            # Если нет переноса строки, ищем пробел
            safe_break = text.rfind(' ', current_pos, end_pos)
        
        if safe_break == -1 or safe_break == current_pos:
            # Если нет пробела, режем по максимальной длине
            safe_break = end_pos
        
        chunks.append(text[current_pos:safe_break])
        current_pos = safe_break + (1 if text[safe_break:safe_break+1] in ['\n', ' '] else 0)
    
    return chunks


async def send_long_html_message(message: Message, text: str, max_length: int = 4096) -> None:
    """
    Отправляет длинное HTML сообщение, разбивая его на части при необходимости.
    
    Args:
        message: Сообщение для ответа
        text: HTML текст для отправки
        max_length: Максимальная длина одного сообщения
    """
    chunks = split_long_html_message(text, max_length)
    
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


# Для обратной совместимости - устаревшие функции MarkdownV2
def escape_markdown_v2(text: str) -> str:
    """
    УСТАРЕВШАЯ ФУНКЦИЯ: Используйте escape_html() вместо этой.
    
    Экранирует спецсимволы для Telegram MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)


def send_long_message_v2(text: str, max_length: int = 4096) -> list[str]:
    """
    УСТАРЕВШАЯ ФУНКЦИЯ: Используйте split_long_html_message() вместо этой.
    
    Разбивает длинное сообщение на части для MarkdownV2, сохраняя форматирование.
    """
    # Сначала экранируем весь текст
    escaped_text = escape_markdown_v2(text)
    
    if len(escaped_text) <= max_length:
        return [escaped_text]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(escaped_text):
        # Определяем границу следующего чанка
        end_pos = current_pos + max_length
        
        if end_pos >= len(escaped_text):
            chunks.append(escaped_text[current_pos:])
            break
        
        # Ищем удобное место для разрыва (по переносу строки)
        safe_break = escaped_text.rfind('\n', current_pos, end_pos)
        if safe_break == -1 or safe_break == current_pos:
            safe_break = escaped_text.rfind(' ', current_pos, end_pos)
        
        if safe_break == -1 or safe_break == current_pos:
            safe_break = end_pos
        
        chunks.append(escaped_text[current_pos:safe_break])
        current_pos = safe_break + (1 if escaped_text[safe_break:safe_break+1] in ['\n', ' '] else 0)
    
    return chunks