"""Сборка клавиатур в зависимости от роли пользователя."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню: команды пользователя + админская статистика."""
    buttons = [
        [KeyboardButton(text="/help"), KeyboardButton(text="/img")],
        [KeyboardButton(text="/stats"), KeyboardButton(text="/reset")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="/stat"), KeyboardButton(text="/update")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)