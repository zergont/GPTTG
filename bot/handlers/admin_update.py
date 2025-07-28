"""Админская команда для ручного обновления бота."""
import asyncio
import subprocess
from pathlib import Path
from aiogram import Router, F, types

from bot.config import settings
from bot.utils.log import logger

router = Router(name="admin_update")

@router.message(F.text.casefold() == "/update")
async def cmd_update(message: types.Message):
    """Команда для ручного обновления бота (только для админа)."""
    if message.from_user.id != settings.admin_id:
        return  # игнорируем остальных
    
    await message.answer("⚙️ Запускаю обновление...")
    
    try:
        # Определяем путь к скрипту относительно проекта
        project_root = Path(__file__).parent.parent.parent
        update_script = project_root / "update_bot.sh"
        
        # Проверяем существование скрипта
        if not update_script.exists():
            await message.answer("❌ Скрипт обновления не найден")
            return
        
        # Запускаем скрипт обновления
        proc = await asyncio.create_subprocess_exec(
            "sudo", "bash", str(update_script), "--no-restart",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(project_root)
        )
        
        stdout, _ = await proc.communicate()
        
        # Обрабатываем результат
        if proc.returncode == 0:
            # Показываем последние 1500 символов вывода
            output = stdout.decode(errors="ignore")
            snippet = output[-1500:] if output else "(вывод пуст)"
            
            await message.answer(
                f"✅ Обновление завершено успешно:\n<pre>{snippet}</pre>",
                parse_mode="HTML"
            )
            logger.info("Ручное обновление через /update завершено успешно")
        else:
            # Показываем ошибку
            error_output = stdout.decode(errors="ignore")
            error_snippet = error_output[-1000:] if error_output else "Неизвестная ошибка"
            
            await message.answer(
                f"❌ Ошибка обновления:\n<pre>{error_snippet}</pre>",
                parse_mode="HTML"
            )
            logger.error(f"Ошибка ручного обновления: {proc.returncode}")
            
    except Exception as e:
        await message.answer(f"❌ Критическая ошибка обновления: {str(e)[:200]}")
        logger.error(f"Критическая ошибка при ручном обновлении: {e}")