"""Командные хендлеры: /start, /help, /img, /reset, /stats, /stat, /models, /setmodel."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
import asyncio
import os
import subprocess
from pathlib import Path

from bot.config import settings, VERSION
from bot.keyboards import main_kb
from bot.utils.openai import OpenAIClient
from bot.utils.db import get_conn, get_user_display_name
from bot.utils.progress import show_progress_indicator
from bot.utils.html import send_long_html_message
from bot.utils.errors import error_handler

router = Router()


class ImgGenStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_format = State()


# ——— /start —————————————————————————————————————————————— #
@router.message(F.text == "/start")
async def cmd_start(msg: Message):
    """Стартовое сообщение с приветствием."""
    welcome_text = (
        f"👋 Привет, {msg.from_user.first_name or 'друг'}!\n\n"
        f"Я — умный ассистент на базе OpenAI Responses API. Умею:\n\n"
        f"💬 Отвечать на questions и поддерживать беседу\n"
        f"🖼 Анализировать изображения с подписями\n" 
        f"🎤 Распознавать голосовые сообщения\n"
        f"🎨 Генерировать картинки по описанию\n\n"
        f"Просто напишите мне что-нибудь или используйте /help для справки!"
    )
    await msg.answer(welcome_text, reply_markup=main_kb(msg.from_user.id == settings.admin_id))


# ——— /help —————————————————————————————————————————————— #
@router.message(F.text == "/help")
async def cmd_help(msg: Message):
    """Выводит краткую справку."""
    
    help_lines = [
        "🤖 <b>Доступные команды:</b>",
        "",
        "💬 Просто пишите мне — я отвечу",
        "🖼 Отправьте фото с подписью — проанализирую",
        "🎤 Отправьте голосовое — распознаю и отвечу",
        "📄 Отправьте документ — прочитаю и проанализирую",
        "",
        "<b>Команды:</b>",
        "/start — приветствие и информация о боте",
        "/help — эта справка",
        "/img &lt;промпт&gt; — сгенерировать картинку",
        "/web &lt;запрос&gt; — выполнить веб-поиск",  # Добавлено описание команды
        "/cancel — отменить текущую операцию",
        "/reset — очистить историю контекста",
        "/stats — показать личные расходы",
    ]
    
    if msg.from_user.id == settings.admin_id:
        help_lines.extend([
            "",
            "<b>Админские команды:</b>",
            "/stat — общая статистика",
            "/models — показать доступные модели",
            "/setmodel — изменить текущую модель",
            "/status — статус системы и служб",
            "/update — проверить и обновить бота",
            "/checkmodel — проверить совместимость модели"
        ])
    
    help_text = "\n".join(help_lines)
    await send_long_html_message(msg, help_text)


# ——— /status (админ) —————————————————————————————————————————— #
@router.message(F.text == "/status")
async def cmd_status(msg: Message):
    """Показывает статус системы (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    import subprocess

    # Проверяем статус службы gpttg-update.service
    service_name = "gpttg-update.service"
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            status_text = result.stdout
        else:
            status_text = result.stderr

        # Анализируем код завершения
        if "failed" in status_text or "exit-code" in status_text:
            await msg.answer(
                f"❌ <b>Служба {service_name} завершилась с ошибкой:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>Служба {service_name} работает корректно:</b>\n\n<pre>{status_text}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке статуса службы: {str(e)}")
        
    # import os
    
    # Определяем базовую директорию проекта
    bot_dir = Path(__file__).parent.parent  # из bot/handlers/ в bot/
    project_root = bot_dir.parent  # из bot/ в корень проекта
    
    # Проверяем файл блокировки
    lock_file = project_root / "gpttg-bot.lock"
    lock_status = "🔒 Активна" if lock_file.exists() else "🔓 Отсутствует"
    
    if lock_file.exists():
        try:
            with open(lock_file, 'r') as f:
                lock_pid = f.read().strip()
            lock_info = f"(PID: {lock_pid})"
            lock_status += f" {lock_info}"
        except Exception:
            lock_status += " (данные недоступны)"
    
    # Проверяем количество процессов бота
    process_count = "неизвестно"
    try:
        import subprocess
        if settings.is_windows:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python*'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                processes = [line for line in result.stdout.split('\n') if 'python' in line.lower()]
                process_count = len(processes)
        else:
            # Linux: используем простой метод
            result = subprocess.run(['pgrep', '-f', 'bot.main'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                process_count = len([p for p in result.stdout.strip().split('\n') if p])
    except Exception as e:
        process_count = f"ошибка: {str(e)[:30]}..."
    
    # Проверяем systemd службы (только для Linux)
    systemd_services = []
    if settings.is_linux:
        services_to_check = [
            ("gpttg-bot.service", "Основная служба бота"),
            ("gpttg-update.service", "Служба автообновления"),
            ("gpttg-update.timer", "Таймер автообновления")
        ]
        
        for service_name, description in services_to_check:
            try:
                # Проверяем статус службы
                result = subprocess.run(
                    ['systemctl', 'is-active', service_name],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    status = result.stdout.strip()
                    if status == "active":
                        icon = "✅"
                        status_text = "активна"
                    elif status == "inactive":
                        # Для oneshot служб (gpttg-update.service) inactive - это нормально
                        if service_name == "gpttg-update.service":
                            icon = "⚫"
                            status_text = "готова к запуску (oneshot)"
                        else:
                            icon = "⚫"
                            status_text = "неактивна"
                    elif status == "failed":
                        icon = "❌"
                        status_text = "сбой"
                    else:
                        icon = "⚠️"
                        status_text = status
                else:
                    # Проверяем существование unit файла
                    try:
                        check_result = subprocess.run(
                            ['systemctl', 'cat', service_name],
                            capture_output=True, text=True, timeout=3
                        )
                        if check_result.returncode == 0:
                            # Служба найдена, но неактивна
                            if service_name == "gpttg-update.service":
                                icon = "⚫"
                                status_text = "готова к запуску (oneshot, unit найден)"
                            else:
                                icon = "⚫"
                                status_text = "неактивна (unit найден)"
                        else:
                            icon = "❓"
                            status_text = "не найдена (unit отсутствует)"
                    except Exception:
                        icon = "❓"
                        status_text = "не найдена"
                
                # Для timer также проверяем enabled статус и последний запуск
                if service_name.endswith('.timer'):
                    try:
                        enabled_result = subprocess.run(
                            ['systemctl', 'is-enabled', service_name],
                            capture_output=True, text=True, timeout=3
                        )
                        if enabled_result.returncode == 0:
                            enabled_status = enabled_result.stdout.strip()
                            if enabled_status == "enabled":
                                status_text += " (включен)"
                            else:
                                status_text += f" ({enabled_status})"
                        
                        # Проверяем информацию о последнем запуске
                        last_trigger_result = subprocess.run(
                            ['systemctl', 'show', service_name, '--property=LastTriggerUSec'],
                            capture_output=True, text=True, timeout=3
                        )
                        if last_trigger_result.returncode == 0:
                            last_trigger = last_trigger_result.stdout.strip()
                            if "LastTriggerUSec=0" not in last_trigger and "LastTriggerUSec=n/a" not in last_trigger:
                                # Получаем более читаемую информацию о времени
                                next_trigger_result = subprocess.run(
                                    ['systemctl', 'show', service_name, '--property=NextElapseUSecRealtime'],
                                    capture_output=True, text=True, timeout=3
                                )
                                if next_trigger_result.returncode == 0:
                                    status_text += " (работает)"
                        
                    except Exception:
                        pass
                
                # Для update.service проверяем, существует ли unit файл
                if service_name == "gpttg-update.service" and "не найдена" in status_text:
                    try:
                        # Проверяем, есть ли файл в /etc/systemd/system/
                        file_check = subprocess.run(
                            ['test', '-f', f'/etc/systemd/system/{service_name}'],
                            timeout=2
                        )
                        if file_check.returncode == 0:
                            status_text += " (файл существует, нужен daemon-reload?)"
                        else:
                            status_text += " (файл не установлен)"
                    except Exception:
                        pass
                
                systemd_services.append(f"{icon} {service_name}: {status_text}")
                
            except subprocess.TimeoutExpired:
                systemd_services.append(f"⏳ {service_name}: проверка превысила время ожидания")
            except Exception as e:
                systemd_services.append(f"❓ {service_name}: ошибка проверки")
    
        # Добавляем дополнительную информацию о таймере автообновления
        if any("gpttg-update.timer" in service for service in systemd_services):
            try:
                # Получаем информацию о следующем запуске
                next_run_result = subprocess.run(
                    ['systemctl', 'list-timers', '--no-legend', 'gpttg-update.timer'],
                    capture_output=True, text=True, timeout=5
                )
                if next_run_result.returncode == 0 and next_run_result.stdout.strip():
                    timer_info = next_run_result.stdout.strip().split()
                    if len(timer_info) >= 2:
                        next_run = " ".join(timer_info[:2])  # Берем дату и время
                        systemd_services.append(f"📅 Следующий запуск автообновления: {next_run}")
                        
                # Проверяем логи последнего запуска службы автообновления
                last_update_result = subprocess.run(
                    ['journalctl', '-u', 'gpttg-update.service', '--no-pager', '-n', '1', '--output=short-iso'],
                    capture_output=True, text=True, timeout=5
                )
                if last_update_result.returncode == 0 and last_update_result.stdout.strip():
                    lines = last_update_result.stdout.strip().split('\n')
                    if lines:
                        last_line = lines[-1]
                        if last_line:
                            # Извлекаем дату из лога
                            parts = last_line.split()
                            if len(parts) >= 2:
                                last_run_date = f"{parts[0]} {parts[1][:8]}"  # Дата и время без миллисекунд
                                systemd_services.append(f"📊 Последний запуск автообновления: {last_run_date}")
                            
            except Exception:
                pass
                
    # Проверяем системные файлы
    version_files = []
    
    # Файлы в корне проекта
    root_files = [".env", "update_bot.sh"]
    for file_name in root_files:
        file_path = project_root / file_name
        if file_path.exists():
            try:
                size = file_path.stat().st_size
                version_files.append(f"✅ {file_name} ({size} байт)")
            except Exception:
                version_files.append(f"⚠️ {file_name} (ошибка чтения)")
        else:
            version_files.append(f"❌ {file_name} (отсутствует)")
    
    # База данных
    db_file = bot_dir / "bot.sqlite"
    if db_file.exists():
        try:
            size = db_file.stat().st_size
            version_files.append(f"✅ bot.sqlite ({size} байт)")
        except Exception:
            version_files.append(f"⚠️ bot.sqlite (ошибка чтения)")
    else:
        version_files.append(f"❌ bot.sqlite (отсутствует)")
    
    # Информация о платформе
    platform_info = f"{settings.platform} ({'dev' if settings.is_development else 'prod'})"
    
    # Формируем статус
    status_text = (
        f"🔧 <b>Статус системы:</b>\n\n"
        f"📋 Версия бота: <code>{VERSION}</code>\n"
        f"🖥️ Платформа: <code>{platform_info}</code>\n"
        f"🔒 Блокировка экземпляра: {lock_status}\n"
        f"⚙️ Процессов bot.main: <code>{str(process_count)}</code>\n\n"
    )
    
    # Добавляем информацию о systemd службах
    if systemd_services:
        status_text += f"🔧 <b>Системные службы:</b>\n"
        for service_info in systemd_services:
            status_text += f"  {service_info}\n"
        
        # Проверяем, есть ли проблемы с службами, и добавляем рекомендации
        if any("не найдена" in service and "gpttg-update.service" in service and "unit отсутствует" in service for service in systemd_services):
            status_text += "\n💡 <b>Рекомендация:</b> Служба автообновления не установлена.\n"
            status_text += "Для установки выполните:\n"
            status_text += "<code>sudo bot/deploy/install.sh</code>\n"
        
        status_text += "\n"
    
    status_text += f"💾 <b>Системные файлы:</b>\n"
    for file_info in version_files:
        status_text += f"  {file_info}\n"
    
    await send_long_html_message(msg, status_text)


# ——— /models (админ) —————————————————————————————————————————— #
@router.message(F.text == "/models")
@error_handler("models_command")
async def cmd_models(msg: Message):
    """Показывает доступные модели (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    current_model = await OpenAIClient.get_current_model()
    models = await OpenAIClient.get_available_models()
    
    models_text = f"🤖 <b>Доступные модели:</b>\n\n"
    models_text += f"🔸 <b>Текущая модель:</b> <code>{current_model}</code>\n\n"
    
    for model in models:
        status = "✅" if model['id'] == current_model else "⚪"
        models_text += f"{status} <code>{model['id']}</code>\n"
    
    models_text += f"\n💡 <i>Не все модели поддерживают текст и изображения! При выборе несовместимой модели бот переключится на модель gpt-4о-mini</i>"
    models_text += f"\nИспользуйте /setmodel для смены модели"
    
    await send_long_html_message(msg, models_text)
        

# ——— /setmodel (админ) —————————————————————————————————————————— #
@router.message(F.text == "/setmodel")
@error_handler("setmodel_command")
async def cmd_setmodel(msg: Message):
    """Показывает inline клавиатуру для выбора модели (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    current_model = await OpenAIClient.get_current_model()
    models = await OpenAIClient.get_available_models()
    
    # Создаем inline клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for model in models:
        status = "✅ " if model['id'] == current_model else ""
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{status}{model['id']}",
                callback_data=f"setmodel:{model['id']}"
            )
        ])
    
    await msg.answer(
        f"🤖 <b>Выберите модель:</b>\n\nТекущая: <code>{current_model}</code>",
        reply_markup=keyboard
    )


# ——— Callback для смены модели —————————————————————————————————————————— #
@router.callback_query(F.data.startswith("setmodel:"))
@error_handler("setmodel_callback")
async def callback_setmodel(callback: CallbackQuery):
    """Обрабатывает выбор модели через inline кнопку."""
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    model_id = callback.data.split(":", 1)[1]
    
    # Устанавливаем новую модель
    await OpenAIClient.set_current_model(model_id)
    
    await callback.message.edit_text(
        f"✅ <b>Модель изменена!</b>\n\nТекущая модель: <code>{model_id}</code>\n\n"
        f"Все новые запросы будут использовать эту модель."
    )
    
    await callback.answer("✅ Модель успешно изменена!")


# ——— /reset —————————————————————————————————————————————— #
@router.message(F.text.startswith("/reset"))
async def cmd_reset(msg: Message, state: FSMContext):
    """Удаляет сохранённый previous_response_id и все файлы OpenAI для чата."""
    # Удаляем файлы из OpenAI и БД
    await OpenAIClient.delete_files_by_chat(msg.chat.id)
    # Очищаем историю чата
    async with get_conn() as db:
        await db.execute(
            "DELETE FROM chat_history WHERE chat_id = ?",
            (msg.chat.id,)
        )
        await db.commit()
    await msg.answer("🗑 История и файлы очищены! Следующий запрос начнет новый диалог.", 
                    reply_markup=main_kb(msg.from_user.id == settings.admin_id))


# ——— /stats —————————————————————————————————————————————— #
@router.message(F.text.startswith("/stats"))
async def cmd_stats(msg: Message):
    """Показывает расходы конкретного пользователя."""
    
    async with get_conn() as db:
        # Общие расходы
        cur = await db.execute(
            "SELECT COALESCE(SUM(cost),0) FROM usage WHERE user_id = ?",
            (msg.from_user.id,),
        )
        (total,) = await cur.fetchone()
        
        # Разбивка по моделям
        cur = await db.execute(
            """SELECT model, COUNT(*) as requests, COALESCE(SUM(cost),0) as model_cost 
               FROM usage WHERE user_id = ? GROUP BY model ORDER BY model_cost DESC""",
            (msg.from_user.id,)
        )
        models = await cur.fetchall()
    
    # Формируем статистику
    stats_text = f"📊 <b>Ваша статистика:</b>\n\nОбщие расходы: <code>${total:.4f}</code>\n\n"
    
    if models:
        stats_text += "<b>По моделям:</b>\n"
        for model, requests, cost in models:
            stats_text += f"• <code>{model}</code>: {requests} запросов — <code>${cost:.4f}</code>\n"
    else:
        stats_text += "Пока нет данных об использовании."
    
    await send_long_html_message(msg, stats_text)


# ——— /stat (админ) —————————————————————————————————————————— #
@router.message(F.text.startswith("/stat"))
async def cmd_stat(msg: Message):
    """Агрегированная статистика для администратора."""
    if msg.from_user.id != settings.admin_id:
        return

    async with get_conn() as db:
        current_model = await OpenAIClient.get_current_model()
        
        (day_total,) = await (await db.execute(
            "SELECT COALESCE(SUM(cost),0) FROM usage WHERE ts >= DATETIME('now','-1 day')",
        )).fetchone()

        (week_total,) = await (await db.execute(
            "SELECT COALESCE(SUM(cost),0) FROM usage WHERE ts >= DATETIME('now','-7 day')",
        )).fetchone()

        (month_total,) = await (await db.execute(
            "SELECT COALESCE(SUM(cost),0) FROM usage WHERE ts >= DATETIME('now','-1 month')",
        )).fetchone()

        rows = await (await db.execute(
            "SELECT user_id, SUM(cost) AS c FROM usage GROUP BY user_id ORDER BY c DESC LIMIT 10",
        )).fetchall()

    # Формируем топ с именами пользователей
    leaderboard_lines = []
    for user_id, cost in rows:
        display_name = await get_user_display_name(user_id)
        leaderboard_lines.append(f"• {display_name} — <code>${cost:.4f}</code>")
    
    leaderboard = "\n".join(leaderboard_lines) or "—"

    # Формируем статистику
    stat_text = (
        f"📈 <b>Общая статистика:</b>\n\n"
        f"🤖 Текущая модель: <code>{current_model}</code>\n\n"
        f"📅 За сутки: <code>${day_total:.4f}</code>\n"
        f"📅 За неделю: <code>${week_total:.4f}</code>\n"
        f"📅 За месяц: <code>${month_total:.4f}</code>\n\n"
        f"🏆 <b>Топ-10 пользователей:</b>\n{leaderboard}"
    )
    
    await send_long_html_message(msg, stat_text)


# ——— /img —————————————————————————————————————————————— #
@router.message(F.text == "/img")
async def cmd_img(msg: Message, state: FSMContext):
    """Запрашиваем у пользователя описание для генерации картинки."""
    await msg.answer(
        "🎨 <b>Генерация изображения</b>\n\n"
        "Опишите, что нарисовать (например: 'Кот в космосе', 'Горы на закате', ...).\n\n"
        "💡 Для отмены отправьте: <code>/cancel</code> или <code>отмена</code>",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ImgGenStates.waiting_for_prompt)


@router.message(ImgGenStates.waiting_for_prompt)
async def imggen_get_prompt(msg: Message, state: FSMContext):
    """Получаем промпт, спрашиваем формат."""
    # Проверяем команды отмены
    if msg.text and msg.text.lower() in ['/cancel', '/отмена', 'отмена', 'cancel']:
        await msg.answer("❌ Генерация изображения отменена.", 
                        reply_markup=main_kb(msg.from_user.id == settings.admin_id))
        await state.clear()
        return
    
    await state.update_data(prompt=msg.text)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вертикальный (1024x1792)", callback_data="img_fmt_vert")],
            [InlineKeyboardButton(text="Горизонтальный (1792x1024)", callback_data="img_fmt_horiz")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="img_cancel")]
        ]
    )
    await msg.answer("Выберите формат изображения:", reply_markup=kb)
    await state.set_state(ImgGenStates.waiting_for_format)


@router.callback_query(ImgGenStates.waiting_for_format)
@error_handler("img_generation")
async def imggen_get_format(callback: CallbackQuery, state: FSMContext):
    """Получаем формат, генерируем картинку."""
    # Проверяем, если пользователь нажал отмену
    if callback.data == "img_cancel":
        await callback.answer("❌ Генерация изображения отменена")
        await callback.message.edit_text("❌ Генерация изображения отменена.")
        await state.clear()
        return
    
    data = await state.get_data()
    prompt = data.get("prompt") or "Смешной кот"
    if callback.data == "img_fmt_vert":
        size = "1024x1792"
    else:
        size = "1792x1024"
    # Сразу отвечаем на callback, чтобы Telegram не выдал ошибку
    await callback.answer()
    progress_task = None
    try:
        progress_task = asyncio.create_task(
            show_progress_indicator(callback.bot, callback.message.chat.id, max_time=60)
        )
        url = await OpenAIClient.dalle(prompt, size, callback.message.chat.id, callback.from_user.id)
        if not url:
            raise ValueError("Не удалось получить изображение.")
        await callback.message.answer_photo(url, caption=f"🖼 {prompt}")
    finally:
        if progress_task and not progress_task.done():
            progress_task.cancel()
    await state.clear()


# ——— /cancel (глобальная отмена) —————————————————————————————————————————— #
@router.message(F.text.in_(["/cancel", "/отмена"]))
async def cmd_cancel(msg: Message, state: FSMContext):
    """Универсальная команда отмены для любого состояния FSM."""
    current_state = await state.get_state()
    
    if current_state is None:
        await msg.answer("❌ Нет активных операций для отмены.", 
                        reply_markup=main_kb(msg.from_user.id == settings.admin_id))
        return
    
    await state.clear()
    
    # Определяем, какая операция была отменена
    if current_state in ["ImgGenStates:waiting_for_prompt", "ImgGenStates:waiting_for_format"]:
        operation = "генерация изображения"
    else:
        operation = "текущая операция"
    
    await msg.answer(f"❌ {operation.capitalize()} отменена.", 
                    reply_markup=main_kb(msg.from_user.id == settings.admin_id))


# ——— /checkmodel (админ) —————————————————————————————————————————— #
@router.message(F.text == "/checkmodel")
@error_handler("checkmodel_command")
async def cmd_checkmodel(msg: Message):
    """Проверяет текущую модель (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    from bot.utils.openai.models import ModelsManager

    current_model = await ModelsManager.get_current_model()
    models = await ModelsManager.get_available_models()
    available_ids = {m['id'] for m in models}

    is_available = current_model in available_ids

    status_icon = "✅" if is_available else "❌"
    status_text = "модель доступна" if is_available else "модель не найдена среди доступных"

    response_text = (
        f"🔍 <b>Текущая модель:</b> <code>{current_model}</code>\n"
        f"{status_icon} Статус: <b>{status_text}</b>\n\n"
        f"<b>Действия:</b>\n"
        f"• /models — показать доступные модели\n"
        f"• /setmodel — сменить модель"
    )

    if not is_available:
        response_text += f"\n\n⚡ <b>Рекомендация:</b> выберите существующую модель через /setmodel"

    await send_long_html_message(msg, response_text)


# ——— /web —————————————————————————————————————————————— #
@router.message(F.text.startswith("/web"))
@error_handler("web_command")
async def cmd_web(msg: Message):
    """Выполняет веб-поиск через OpenAI Responses API."""
    if msg.from_user.id != settings.admin_id:
        await msg.answer("❌ У вас нет прав для использования этой команды.")
        return

    # Извлекаем запрос из команды
    query = msg.text[len("/web"):].strip()
    if not query:
        await msg.answer("❌ Пожалуйста, укажите запрос для веб-поиска. Пример: <code>/web Какая погода в Риме?</code>", parse_mode="HTML")
        return

    await msg.answer(f"🔍 Выполняю веб-поиск для запроса: <b>{query}</b>", parse_mode="HTML")

    # Формируем запрос к OpenAI Responses API
    content = [{"type": "message", "role": "user", "content": query}]
    tools = [{"type": "web_search_preview"}]

    try:
        # Отправляем запрос в OpenAI API
        response_text = await OpenAIClient.responses_request(
            chat_id=msg.chat.id,
            user_content=content,
            tools=tools
        )
        # Отправляем результат пользователю
        await msg.answer(f"🌐 <b>Результат веб-поиска:</b>\n\n{response_text}", parse_mode="HTML")
    except Exception as e:
        await msg.answer(f"❌ Ошибка при выполнении веб-поиска: {str(e)}")