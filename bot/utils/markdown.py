def escape_markdown_v2(text: str) -> str:
    """
    Экранирует спецсимволы для Telegram MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)


def send_long_message_v2(text: str, max_length: int = 4096) -> list[str]:
    """
    Разбивает длинное сообщение на части для MarkdownV2, сохраняя форматирование.
    
    Args:
        text: Исходный текст для отправки
        max_length: Максимальная длина одного сообщения
        
    Returns:
        list[str]: Список частей сообщения (уже экранированных для MarkdownV2)
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
            # Последний кусок
            chunks.append(escaped_text[current_pos:])
            break
        
        # Ищем удобное место для разрыва (по переносу строки)
        safe_break = escaped_text.rfind('\n', current_pos, end_pos)
        if safe_break == -1 or safe_break == current_pos:
            # Если нет переноса строки, ищем пробел
            safe_break = escaped_text.rfind(' ', current_pos, end_pos)
        
        if safe_break == -1 or safe_break == current_pos:
            # Если нет пробела, режем по максимальной длине
            safe_break = end_pos
        
        chunks.append(escaped_text[current_pos:safe_break])
        current_pos = safe_break + (1 if escaped_text[safe_break:safe_break+1] in ['\n', ' '] else 0)
    
    return chunks


def format_file_analysis_v2(filename: str, content: str) -> str:
    """
    Красивое форматирование анализа файла для MarkdownV2.

    Args:
        filename: Имя файла
        content: Содержимое ответа

    Returns:
        str: Отформатированный текст для MarkdownV2
    """
    safe_filename = escape_markdown_v2(filename)
    safe_content = escape_markdown_v2(content)

    return f"📄 *Анализ файла* `{safe_filename}`:\n\n{safe_content}"


def format_system_info_v2(version: str, platform: str, lock_status: str,
                         process_count: str, files: list[str], tools: list[str]) -> str:
    """
    Красивое форматирование системной информации для MarkdownV2.
    """
    safe_version = escape_markdown_v2(version)
    safe_platform = escape_markdown_v2(platform)
    safe_process_count = escape_markdown_v2(str(process_count))

    text = (
        f"🔧 *Статус системы:*\n\n"
        f"📋 *Версия бота:* `{safe_version}`\n"
        f"🖥️ *Платформа:* {safe_platform}\n"
        f"🔒 *Блокировка экземпляра:* {lock_status}\n"
        f"⚙️ *Процессов bot\\.main:* {safe_process_count}\n\n"
        f"💾 *Системные файлы:*\n"
    )

    for file_info in files:
        text += f"  {file_info}\n"

    if tools:
        text += f"\n🛠️ *Системные утилиты:*\n"
        for tool_info in tools[:5]:
            text += f"  {tool_info}\n"

    return text