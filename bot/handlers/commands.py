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
from bot.utils.openai_client import OpenAIClient
from bot.utils.db import get_conn, get_user_display_name
from bot.utils.progress import show_progress_indicator
from bot.utils.html import send_long_html_message

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
            "/status — статус системы",
            "/update — ручное обновление бота"
        ])
    
    help_text = "\n".join(help_lines)
    await send_long_html_message(msg, help_text)


# ——— /status (админ) —————————————————————————————————————————— #
@router.message(F.text == "/status")
async def cmd_status(msg: Message):
    """Показывает статус системы (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    import os
    
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
        f"💾 <b>Системные файлы:</b>\n"
    )
    
    for file_info in version_files:
        status_text += f"  {file_info}\n"
    
    await send_long_html_message(msg, status_text)


# ——— /models (админ) —————————————————————————————————————————— #
@router.message(F.text == "/models")
async def cmd_models(msg: Message):
    """Показывает доступные модели (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    try:
        current_model = await OpenAIClient.get_current_model()
        models = await OpenAIClient.get_available_models()
        
        models_text = f"🤖 <b>Доступные модели:</b>\n\n"
        models_text += f"🔸 <b>Текущая модель:</b> <code>{current_model}</code>\n\n"
        
        for model in models[:10]:  # Показываем первые 10 моделей
            status = "✅" if model['id'] == current_model else "⚪"
            models_text += f"{status} <code>{model['id']}</code>\n"
        
        models_text += f"\nИспользуйте /setmodel для смены модели"
        
        await send_long_html_message(msg, models_text)
        
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
            f"🤖 <b>Выберите модель:</b>\n\nТекущая: <code>{current_model}</code>",
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
            f"✅ <b>Модель изменена!</b>\n\nТекущая модель: <code>{model_id}</code>\n\n"
            f"Все новые запросы будут использовать эту модель."
        )
        
        await callback.answer("✅ Модель успешно изменена!")
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


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