"""Командные хендлеры: /start, /help, /img, /reset, /stats, /stat, /models, /setmodel."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
import asyncio
import os
from pathlib import Path

from bot.config import settings
from bot.keyboards import main_kb
from bot.utils.openai_client import OpenAIClient
from bot.utils.db import get_conn, get_user_display_name
from bot.utils.progress import show_progress_indicator

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
        f"💬 Отвечать на вопросы и поддерживать беседу\n"
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
    from bot.utils.markdown import send_long_message_v2
    
    help_lines = [
        "🤖 *Доступные команды:*",
        "",
        "💬 Просто пишите мне — я отвечу",
        "🖼 Отправьте фото с подписью — проанализирую",
        "🎤 Отправьте голосовое — распознаю и отвечу",
        "📄 Отправьте документ — прочитаю и проанализирую",
        "",
        "*Команды:*",
        "/start — приветствие и информация о боте",
        "/help — эта справка",
        "/img <промпт> — сгенерировать картинку",
        "/reset — очистить историю контекста",
        "/stats — показать личные расходы",
    ]
    
    from bot.keyboards import ADMIN_INLINE_KB
    if msg.from_user.id == settings.admin_id:
        help_lines.extend([
            "",
            "*Админские команды:*",
            "/stat — общая статистика",
            "/models — показать доступные модели",
            "/setmodel — изменить текущую модель",
            "/status — статус системы"
        ])
        keyboard = ADMIN_INLINE_KB
    else:
        keyboard = main_kb(False)
    
    # Применяем старый подход БЕЗ предварительного экранирования
    help_text = "\n".join(help_lines)
    chunks = send_long_message_v2(help_text)  # Экранирование происходит внутри функции
    for i, chunk in enumerate(chunks):
        # Добавляем клавиатуру только к последнему сообщению
        current_keyboard = keyboard if i == len(chunks) - 1 else None
        await msg.answer(chunk, parse_mode="MarkdownV2", reply_markup=current_keyboard)


# ——— /status (админ) —————————————————————————————————————————— #
@router.message(F.text == "/status")
async def cmd_status(msg: Message):
    """Показывает статус системы (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    from bot.config import VERSION
    import os
    
    # Определяем базовую директорию проекта
    # Получаем путь к директории bot/ и поднимаемся на уровень выше
    bot_dir = Path(__file__).parent.parent  # из bot/handlers/ в bot/
    project_root = bot_dir.parent  # из bot/ в корень проекта
    
    # Проверяем файл блокировки (относительно корня проекта)
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
    
    # Проверяем количество процессов бота (с fallback методами)
    process_count = "неизвестно"
    try:
        import subprocess
        if settings.is_windows:
            # Windows: используем tasklist
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python*'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                processes = [line for line in result.stdout.split('\n') if 'python' in line.lower()]
                process_count = len(processes)
        else:
            # Linux: пробуем разные методы
            methods = [
                # Метод 1: pgrep (если установлен)
                (['pgrep', '-f', 'bot.main'], lambda out: len([p for p in out.strip().split('\n') if p])),
                # Метод 2: ps + grep
                (['ps', 'aux'], lambda out: len([line for line in out.split('\n') if 'bot.main' in line])),
                # Метод 3: pidof python3 + проверка
                (['pidof', 'python3'], lambda out: len(out.strip().split()) if out.strip() else 0)
            ]
            
            for cmd, parser in methods:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        process_count = parser(result.stdout)
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
    except Exception as e:
        process_count = f"ошибка: {str(e)[:30]}..."
    
    # Проверяем системные файлы с правильными путями
    version_files = []
    
    # Файлы в корне проекта
    root_files = ["last_version.txt", ".env"]
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
    
    # База данных в папке bot/
    db_file = bot_dir / "bot.sqlite"
    if db_file.exists():
        try:
            size = db_file.stat().st_size
            version_files.append(f"✅ bot.sqlite ({size} байт)")
        except Exception:
            version_files.append(f"⚠️ bot.sqlite (ошибка чтения)")
    else:
        version_files.append(f"❌ bot.sqlite (отсутствует)")
    
    # Добавляем информацию о путях для диагностики
    version_files.append(f"📁 Рабочая директория: {os.getcwd()}")
    version_files.append(f"📁 Корень проекта: {project_root}")
    version_files.append(f"📁 Папка bot: {bot_dir}")
    
    # Проверяем системные утилиты (диагностика)
    system_tools = []
    try:
        import subprocess
        tools_to_check = ['pgrep', 'ps', 'pidof'] if not settings.is_windows else ['tasklist']
        for tool in tools_to_check:
            try:
                result = subprocess.run(['which', tool] if not settings.is_windows else ['where', tool], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    system_tools.append(f"✅ {tool}")
                else:
                    system_tools.append(f"❌ {tool}")
            except Exception:
                system_tools.append(f"❌ {tool}")
    except Exception:
        system_tools = ["❌ Ошибка проверки утилит"]
    
    # Информация о платформе
    platform_info = f"{settings.platform} ({'dev' if settings.is_development else 'prod'})"
    
    # Форматируем статус БЕЗ MarkdownV2 - используем обычный текст
    status_text = (
        f"🔧 Статус системы:\n\n"
        f"📋 Версия бота: {VERSION}\n"
        f"🖥️ Платформа: {platform_info}\n"
        f"🔒 Блокировка экземпляра: {lock_status}\n"
        f"⚙️ Процессов bot.main: {str(process_count)}\n\n"
        f"💾 Системные файлы:\n"
    )
    
    for file_info in version_files:
        status_text += f"  {file_info}\n"
    
    if system_tools:
        status_text += f"\n🛠️ Системные утилиты:\n"
        for tool_info in system_tools[:5]:
            status_text += f"  {tool_info}\n"
    
    # Отправляем без MarkdownV2 - только обычный текст
    if len(status_text) <= 4096:
        await msg.answer(status_text)
    else:
        # Разбиваем на части вручную без экранирования
        chunks = []
        current_pos = 0
        max_length = 4096
        
        while current_pos < len(status_text):
            end_pos = current_pos + max_length
            if end_pos >= len(status_text):
                chunks.append(status_text[current_pos:])
                break
            
            # Ищем удобное место для разрыва
            safe_break = status_text.rfind('\n', current_pos, end_pos)
            if safe_break == -1 or safe_break == current_pos:
                safe_break = status_text.rfind(' ', current_pos, end_pos)
            if safe_break == -1 or safe_break == current_pos:
                safe_break = end_pos
            
            chunks.append(status_text[current_pos:safe_break])
            current_pos = safe_break + (1 if status_text[safe_break:safe_break+1] in ['\n', ' '] else 0)
        
        for chunk in chunks:
            await msg.answer(chunk)


# ——— /models (админ) —————————————————————————————————————————— #
@router.message(F.text == "/models")
async def cmd_models(msg: Message):
    """Показывает доступные модели (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    try:
        from bot.utils.markdown import send_long_message_v2
        
        current_model = await OpenAIClient.get_current_model()
        models = await OpenAIClient.get_available_models()
        
        models_text = f"🤖 *Доступные модели:*\n\n"
        models_text += f"🔸 *Текущая модель:* `{current_model}`\n\n"
        
        for model in models[:10]:  # Показываем первые 10 моделей
            status = "✅" if model['id'] == current_model else "⚪"
            # НЕ экранируем здесь - будет экранировано позже
            models_text += f"{status} `{model['id']}`\n"
        
        models_text += f"\nИспользуйте /setmodel для смены модели"
        
        # Применяем старый красивый подход с ОДНИМ экранированием
        chunks = send_long_message_v2(models_text)
        for chunk in chunks:
            await msg.answer(chunk, parse_mode="MarkdownV2")
        
    except Exception as e:
        await msg.answer(f"❌ Ошибка получения списка моделей: {e}")


# ——— /setmodel (админ) —————————————————————————————————————————— #
@router.message(F.text == "/setmodel")
async def cmd_setmodel(msg: Message):
    """Показывает inline клавиатуру для выбора модели (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    try:
        current_model = await OpenAIClient.get_current_model()
        models = await OpenAIClient.get_available_models()
        
        # Создаем inline клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for model in models[:8]:  # Ограничиваем до 8 моделей
            status = "✅ " if model['id'] == current_model else ""
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{status}{model['id']}",
                    callback_data=f"setmodel:{model['id']}"
                )
            ])
        
        await msg.answer(
            f"🤖 *Выберите модель:*\n\nТекущая: `{current_model}`",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        await msg.answer(f"❌ Ошибка загрузки моделей: {e}")


# ——— Callback для смены модели —————————————————————————————————————————— #
@router.callback_query(F.data.startswith("setmodel:"))
async def callback_setmodel(callback: CallbackQuery):
    """Обрабатывает выбор модели через inline кнопку."""
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    try:
        model_id = callback.data.split(":", 1)[1]
        
        # Устанавливаем новую модель
        await OpenAIClient.set_current_model(model_id)
        
        await callback.message.edit_text(
            f"✅ *Модель изменена!*\n\nТекущая модель: `{model_id}`\n\n"
            f"Все новые запросы будут использовать эту модель.",
            parse_mode="Markdown"
        )
        
        await callback.answer("✅ Модель успешно изменена!")
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ——— /reset —————————————————————————————————————————————— #
@router.message(F.text.startswith("/reset"))
async def cmd_reset(msg: Message):
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
    
    # Форматируем БЕЗ MarkdownV2 - используем обычный текст
    stats_text = f"📊 Ваша статистика:\n\nОбщие расходы: ${total:.4f}\n\n"
    
    if models:
        stats_text += "По моделям:\n"
        for model, requests, cost in models:
            # НЕ экранируем здесь - используем обычный текст
            stats_text += f"• {model}: {requests} запросов — ${cost:.4f}\n"
    else:
        stats_text += "Пока нет данных об использовании."
    
    # Отправляем без MarkdownV2 - только обычный текст
    if len(stats_text) <= 4096:
        await msg.answer(stats_text)
    else:
        # Разбиваем на части вручную без экранирования
        chunks = []
        current_pos = 0
        max_length = 4096
        
        while current_pos < len(stats_text):
            end_pos = current_pos + max_length
            if end_pos >= len(stats_text):
                chunks.append(stats_text[current_pos:])
                break
            
            # Ищем удобное место для разрыва
            safe_break = stats_text.rfind('\n', current_pos, end_pos)
            if safe_break == -1 or safe_break == current_pos:
                safe_break = stats_text.rfind(' ', current_pos, end_pos)
            if safe_break == -1 or safe_break == current_pos:
                safe_break = end_pos
            
            chunks.append(stats_text[current_pos:safe_break])
            current_pos = safe_break + (1 if stats_text[safe_break:safe_break+1] in ['\n', ' '] else 0)
        
        for chunk in chunks:
            await msg.answer(chunk)


# ——— /stat (админ) —————————————————————————————————————————— #
@router.message(F.text.startswith("/stat"))
async def cmd_stat(msg: Message):
    """Агрегированная статистика для администратора."""
    if msg.from_user.id != settings.admin_id:
        return

    async with get_conn() as db:
        # Получаем текущую модель
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
        # НЕ экранируем здесь - используем обычный текст
        leaderboard_lines.append(f"• {display_name} — ${cost:.4f}")
    
    leaderboard = "\n".join(leaderboard_lines) or "—"

    # Форматируем БЕЗ MarkdownV2 - используем обычный текст
    stat_text = (
        f"📈 Общая статистика:\n\n"
        f"🤖 Текущая модель: {current_model}\n\n"
        f"📅 За сутки: ${day_total:.4f}\n"
        f"📅 За неделю: ${week_total:.4f}\n"
        f"📅 За месяц: ${month_total:.4f}\n\n"
        f"🏆 Топ-10 пользователей:\n{leaderboard}"
    )
    
    # Отправляем без MarkdownV2 - только обычный текст
    if len(stat_text) <= 4096:
        await msg.answer(stat_text)
    else:
        # Разбиваем на части вручную без экранирования
        chunks = []
        current_pos = 0
        max_length = 4096
        
        while current_pos < len(stat_text):
            end_pos = current_pos + max_length
            if end_pos >= len(stat_text):
                chunks.append(stat_text[current_pos:])
                break
            
            # Ищем удобное место для разрыва
            safe_break = stat_text.rfind('\n', current_pos, end_pos)
            if safe_break == -1 or safe_break == current_pos:
                safe_break = stat_text.rfind(' ', current_pos, end_pos)
            if safe_break == -1 or safe_break == current_pos:
                safe_break = end_pos
            
            chunks.append(stat_text[current_pos:safe_break])
            current_pos = safe_break + (1 if stat_text[safe_break:safe_break+1] in ['\n', ' '] else 0)
        
        for chunk in chunks:
            await msg.answer(chunk)


# ——— /img —————————————————————————————————————————————— #
@router.message(F.text == "/img")
async def cmd_img(msg: Message, state: FSMContext):
    """Запрашиваем у пользователя описание для генерации картинки."""
    await msg.answer(
        "Опишите, что нарисовать (например: 'Кот в космосе', 'Горы на закате', ...)",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ImgGenStates.waiting_for_prompt)


@router.message(ImgGenStates.waiting_for_prompt)
async def imggen_get_prompt(msg: Message, state: FSMContext):
    """Получаем промпт, спрашиваем формат."""
    await state.update_data(prompt=msg.text)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вертикальный (1024x1792)", callback_data="img_fmt_vert")],
            [InlineKeyboardButton(text="Горизонтальный (1792x1024)", callback_data="img_fmt_horiz")],
        ]
    )
    await msg.answer("Выберите формат изображения:", reply_markup=kb)
    await state.set_state(ImgGenStates.waiting_for_format)


@router.callback_query(ImgGenStates.waiting_for_format)
async def imggen_get_format(callback: CallbackQuery, state: FSMContext):
    """Получаем формат, генерируем картинку."""
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
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка генерации изображения: {e}")
    finally:
        if progress_task and not progress_task.done():
            progress_task.cancel()
    await state.clear()


# ——— /checkupdate (админ) ———————————————————————————————— #
@router.message(F.text == "/checkupdate")
async def cmd_checkupdate(msg: Message):
    """Проверка наличия новой версии (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return
    from bot.main import check_github_version, send_update_prompt, VERSION
    remote_version = await check_github_version()
    if remote_version and remote_version != VERSION:
        await send_update_prompt(msg.bot, msg.from_user.id, VERSION, remote_version)
    else:
        await msg.answer(f"✅ Установлена актуальная версия: {VERSION}")


# Callback для кнопки "Проверить обновления"
@router.callback_query(F.data == "admin_check_update")
async def callback_admin_check_update(callback: CallbackQuery):
    from bot.main import check_github_version, send_update_prompt, VERSION
    remote_version = await check_github_version()
    if remote_version and remote_version != VERSION:
        await send_update_prompt(callback.bot, callback.from_user.id, VERSION, remote_version)
    else:
        await callback.message.answer(f"✅ Установлена актуальная версия: {VERSION}")
    await callback.answer()  # Убрали show_alert=True и текст всплывающего сообщения