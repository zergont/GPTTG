def escape_markdown_v2(text: str) -> str:
    """
    Экранирует спецсимволы для Telegram MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)