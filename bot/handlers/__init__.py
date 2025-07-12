"""Объединение всех роутеров."""
from aiogram import Router
from .commands import router as commands_router
from .text import router as text_router
from .photo import router as photo_router
from .voice import router as voice_router
from .document import router as document_router  # Новый роутер

# Основной роутер, который объединяет все остальные
router = Router()  # вместо main_router = Router()

# Порядок важен: более специфичные хендлеры должны быть выше
router.include_router(commands_router)
router.include_router(photo_router)
router.include_router(voice_router)
router.include_router(document_router)  # Добавляем обработчик документов
router.include_router(text_router)  # Текстовый хендлер должен быть последним