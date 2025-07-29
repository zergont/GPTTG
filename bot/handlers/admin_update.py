"""Админская команда для ручного обновления бота."""
import asyncio
import subprocess
from pathlib import Path
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import settings
from bot.utils.log import logger
from bot.utils.version_checker import update_checker

router = Router(name="admin_update")


@router.message(F.text.casefold() == "/update")
async def cmd_update(message: types.Message):
    """Универсальная команда обновления: проверка + обновление (только для админа)."""
    if message.from_user.id != settings.admin_id:
        return  # игнорируем остальных
    
    await message.answer("🔍 Проверяю наличие обновлений...")
    
    try:
        # Проверяем доступность обновлений
        update_info = await update_checker.check_updates_available()
        
        if update_info.get("error"):
            await message.answer(
                f"❌ <b>Ошибка проверки обновлений:</b>\n"
                f"<code>{update_info['error']}</code>",
                parse_mode="HTML"
            )
            return
        
        # Формируем базовую информацию
        info_text = update_checker.format_update_info(update_info)
        
        # Добавляем информацию о последних коммитах
        if update_info.get("available"):
            # Есть обновления - показываем изменения и предлагаем обновиться
            recent_commits = await update_checker.get_recent_commits(count=3)
            if recent_commits:
                info_text += "\n\n📝 <b>Последние изменения:</b>\n"
                for commit in recent_commits:
                    info_text += f"• <code>{commit['hash']}</code> {commit['message']}\n"
            
            # Создаем кнопки подтверждения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Обновить сейчас", callback_data="update_confirm")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="update_cancel")]
            ])
            
            await message.answer(info_text, parse_mode="HTML", reply_markup=keyboard)
            
        else:
            # Обновления не требуются - показываем статус с дополнительной информацией
            recent_commits = await update_checker.get_recent_commits(count=5)
            if recent_commits:
                info_text += "\n\n📝 <b>Последние коммиты в репозитории:</b>\n"
                for commit in recent_commits[:3]:  # Показываем только 3 последних
                    info_text += f"• <code>{commit['hash']}</code> {commit['message']}\n"
                    info_text += f"  <i>by {commit['author']}, {commit['date']}</i>\n"
            
            await message.answer(info_text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Критическая ошибка при проверке обновлений: {str(e)[:200]}")
        logger.error(f"Критическая ошибка при проверке обновлений: {e}")


@router.callback_query(F.data == "update_confirm")
async def callback_update_confirm(callback: types.CallbackQuery):
    """Подтверждение обновления."""
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.edit_text("⚙️ Запускаю процесс обновления...")
    
    try:
        # Определяем путь к скрипту относительно проекта
        project_root = Path(__file__).parent.parent.parent
        update_script = project_root / "update_bot.sh"
        
        # Проверяем существование скрипта
        if not update_script.exists():
            await callback.message.edit_text("❌ Скрипт обновления не найден")
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
            
            await callback.message.edit_text(
                f"✅ <b>Обновление завершено успешно!</b>\n\n"
                f"<pre>{snippet}</pre>",
                parse_mode="HTML"
            )
            logger.info("Ручное обновление через /update завершено успешно")
        else:
            # Показываем ошибку
            error_output = stdout.decode(errors="ignore")
            error_snippet = error_output[-1000:] if error_output else "Неизвестная ошибка"
            
            await callback.message.edit_text(
                f"❌ <b>Ошибка обновления:</b>\n\n"
                f"<pre>{error_snippet}</pre>",
                parse_mode="HTML"
            )
            logger.error(f"Ошибка ручного обновления: {proc.returncode}")
            
    except Exception as e:
        await callback.message.edit_text(f"❌ Критическая ошибка обновления: {str(e)[:200]}")
        logger.error(f"Критическая ошибка при ручном обновлении: {e}")


@router.callback_query(F.data == "update_cancel")
async def callback_update_cancel(callback: types.CallbackQuery):
    """Отмена обновления."""
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.edit_text("❌ Обновление отменено")