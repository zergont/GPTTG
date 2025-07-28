"""Сборка клавиатур в зависимости от роли пользователя."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import settings


def main_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню: команды пользователя + админская статистика."""
    buttons = [
        [KeyboardButton(text="/help"), KeyboardButton(text="/img")],
        [KeyboardButton(text="/stats"), KeyboardButton(text="/reset")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="/stat"), KeyboardButton(text="/update")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Пример inline‑клавиатуры выбора размера при /img
IMG_SIZE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="256×256", callback_data="img_sz_256")],
        [InlineKeyboardButton(text="512×512", callback_data="img_sz_512")],
        [InlineKeyboardButton(text="1024×1024", callback_data="img_sz_1024")],
    ]
)