"""Командные хендлеры: /start, /help, /img, /reset, /stats, /stat, /models, /setmodel."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
import asyncio

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
            "/checkmodel — проверить совместимость модели",
            "/limits — информация о rate limits",
            "/status — статус системы и служб",
            "/update — проверить и обновить бота",
            "/pricing — цены моделей"
        ])
    
    help_text = "\n".join(help_lines)
    await send_long_html_message(msg, help_text)


# ——— /pricing (админ) —————————————————————————————————————————— #
@router.message(F.text == "/pricing")
@error_handler("pricing_command")
async def cmd_pricing(msg: Message):
    if msg.from_user.id != settings.admin_id:
        return
    from bot.utils.openai.models import ModelsManager
    models = await ModelsManager.get_available_models()
    lines = ["💵 <b>Цены за 1k токенов</b> (input / cached_input / output):\n"]
    for m in models:
        prices = ModelsManager.get_model_prices(m['id'])
        inp = prices.get('input')
        cached = prices.get('cached_input')
        out = prices.get('output')
        if cached is not None:
            lines.append(f"• <code>{m['id']}</code>: ${inp:.5f} / ${cached:.5f} / ${out:.5f}")
        else:
            lines.append(f"• <code>{m['id']}</code>: ${inp:.5f} / ${out:.5f}")
    await send_long_html_message(msg, "\n".join(lines))


# ——— /status (админ) —————————————————————————————————————————— #
@router.message(F.text == "/status")
async def cmd_status(msg: Message):
    """Показывает статус системы (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    import subprocess
    import os
    import platform

    # Определяем базовую директорию проекта
    bot_dir = Path(__file__).parent.parent  # из bot/handlers/ в bot/
    project_root = bot_dir.parent  # из bot/ в корень проекта

    is_windows = settings.is_windows or platform.system().lower() == 'windows'

    # Проверяем файл блокировки (single-instance)
    lock_file = project_root / "gpttg-bot.lock"
    lock_status = "🔓 Отсутствует"
    if lock_file.exists():
        try:
            with open(lock_file, 'r', encoding='utf-8') as f:
                lock_pid_str = f.read().strip()
            lock_pid = int(lock_pid_str)

            # Проверяем, активен ли процесс БЕЗ посылки сигнала на Windows
            running = False
            if is_windows:
                try:
                    import ctypes
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, lock_pid)
                    if handle:
                        ctypes.windll.kernel32.CloseHandle(handle)
                        running = True
                    else:
                        running = False
                except Exception:
                    running = False
            else:
                try:
                    os.kill(lock_pid, 0)  # POSIX: 0 не посылает сигнал, только проверяет
                    running = True
                except ProcessLookupError:
                    running = False
                except PermissionError:
                    running = True

            lock_status = f"🔒 Активна (PID: {lock_pid}, процесс: {'жив' if running else 'мертв'})"
        except Exception:
            lock_status = "⚠️ Файл существует, но прочитать не удалось"

    # Проверяем количество процессов бота
    process_count = "n/a"
    if not is_windows:
        try:
            result = subprocess.run(['pgrep', '-f', 'bot.main'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                pids = [p for p in result.stdout.strip().split('\n') if p]
                process_count = len(pids)
            else:
                process_count = 0
        except Exception as e:
            process_count = f"ошибка: {str(e)[:30]}..."

    # Проверяем systemd службы (только Linux)
    systemd_services = []
    if not is_windows:
        services_to_check = [
            ("gpttg-bot.service", "Основная служба бота"),
            ("gpttg-update.service", "Служба автообновления"),
            ("gpttg-update.timer", "Таймер автообновления")
        ]

        for service_name, description in services_to_check:
            try:
                result = subprocess.run(['systemctl', 'status', service_name], capture_output=True, text=True, timeout=5)
                status_output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
                if "Active: active" in status_output:
                    icon = "✅"
                    status_text = "активна"
                elif "Active: inactive" in status_output and "Result: exit-code" not in status_output:
                    icon = "⚫"
                    status_text = "завершена успешно (oneshot)"
                elif "failed" in status_output or "Result: exit-code" in status_output:
                    icon = "❌"
                    status_text = "сбой"
                else:
                    icon = "⚠️"
                    status_text = "неизвестно"
                systemd_services.append(f"{icon} {service_name}: {status_text}")
            except Exception as e:
                systemd_services.append(f"❓ {service_name}: ошибка проверки ({str(e)[:30]})")

    # Проверяем системные файлы
    version_files = []
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

    # Формируем статус
    status_text = (
        f"🔧 <b>Статус системы:</b>\n\n"
        f"📋 Версия бота: <code>{VERSION}</code>\n"
        f"🖥️ Платформа: <code>{settings.platform} ({'dev' if settings.is_development else 'prod'})</code>\n"
        f"🔒 Блокировка экземпляра: {lock_status}\n"
    )
    if not is_windows:
        status_text += f"⚙️ Процессов bot.main: <code>{str(process_count)}</code>\n\n"

    if systemd_services:
        status_text += f"🔧 <b>Системные службы:</b>\n"
        for service_info in systemd_services:
            status_text += f"  {service_info}\n"
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
@router.callback_query(lambda c: c.data and c.data.startswith("setmodel:"))
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
    """Удаляет сохранённый previous_response_id и все файлы OpenAI для чата. Также очищает все напоминания для этого чата."""
    # Удаляем файлы из OpenAI и БД
    await OpenAIClient.delete_files_by_chat(msg.chat.id)
    # Очищаем историю чата и напоминания
    async with get_conn() as db:
        await db.execute(
            "DELETE FROM chat_history WHERE chat_id = ?",
            (msg.chat.id,)
        )
        await db.execute(
            "DELETE FROM reminders WHERE chat_id = ?",
            (msg.chat.id,)
        )
        await db.commit()
    await msg.answer("🗑 История, файлы и все напоминания очищены! Следующий запрос начнет новый диалог.", 
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
            [InlineKeyboardButton(text="Квадратный (1024x1024)", callback_data="img_fmt_square")],
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
    elif callback.data == "img_fmt_horiz":
        size = "1792x1024"
    elif callback.data == "img_fmt_square":
        size = "1024x1024"
    else:
        size = "1024x1024"
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

    # Информация о rate limits для разных моделей
    rate_limits_info = {
        "gpt-5": "30,000 токенов/минуту",
        "gpt-4o": "150,000 токенов/минуту", 
        "gpt-4o-mini": "200,000 токенов/минуту"
    }
    
    limit_info = rate_limits_info.get(current_model, "неизвестно")

    response_text = (
        f"🔍 <b>Текущая модель:</b> <code>{current_model}</code>\n"
        f"{status_icon} Статус: <b>{status_text}</b>\n"
        f"📊 Лимит токенов: <code>{limit_info}</code>\n\n"
        f"<b>Д действи я:</b>\n"
        f"• /models — показать доступные модели\n"
        f"• /setmodel — сменить модель\n\n"
        f"💡 <b>Совет:</b> gpt-4о-mini имеет наибольший лимит токенов"
    )

    if not is_available:
        response_text += f"\n\n⚡ <b>Рекомендация:</b> выберите существующую модель через /setmodel"

    await send_long_html_message(msg, response_text)


# ——— /limits (админ) —————————————————————————————————————————— #
@router.message(F.text == "/limits")
@error_handler("limits_command")
async def cmd_limits(msg: Message):
    """Показывает информацию о rate limits (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    from bot.utils.openai.models import ModelsManager

    current_model = await ModelsManager.get_current_model()
    
    # Информация о лимитах разных моделей
    model_limits = {
        "gpt-5": {"tokens": "30,000/мин", "requests": "500/мин", "tier": "Tier 5"},
        "gpt-4o": {"tokens": "150,000/мин", "requests": "10,000/мин", "tier": "Tier 5"},
        "gpt-4o-mini": {"tokens": "200,000/мин", "requests": "30,000/мин", "tier": "Tier 5"},
        "gpt-4": {"tokens": "40,000/мин", "requests": "5,000/мин", "tier": "Tier 4"},
        "gpt-3.5-turbo": {"tokens": "90,000/мин", "requests": "10,000/мин", "tier": "Tier 4"}
    }
    
    current_limits = model_limits.get(current_model, {
        "tokens": "неизвестно", 
        "requests": "неизвестно", 
        "tier": "неизвестно"
    })
    
    # Статус текущей модели
    status_emoji = "🟢" if current_model in ["gpt-4o-mini", "gpt-4o"] else "🟡" if current_model == "gpt-5" else "🔴"
    
    response_text = (
        f"📊 <b>Rate Limits Information</b>\n\n"
        f"🤖 <b>Текущая модель:</b> <code>{current_model}</code> {status_emoji}\n"
        f"🎯 <b>Лимиты:</b>\n"
        f"  • Токены: <code>{current_limits['tokens']}</code>\n"
        f"  • Запросы: <code>{current_limits['requests']}</code>\n"
        f"  • Тариф: <code>{current_limits['tier']}</code>\n\n"
        f"📈 <b>Рекомендуемые модели:</b>\n"
        f"🟢 gpt-4о-mini — 200k токенов/мин (лучший выбор)\n"
        f"🟢 gpt-4о — 150k токенов/мин (высокое качество)\n"
        f"🟡 gpt-5 — 30k токенов/мин (новейшая, но ограничения)\n\n"
        f"💡 <b>Настройки бота:</b>\n"
        f"  • Retry: <code>отключен</code> ✅\n"
        f"  • Семафор: <code>1 запрос/чат, {getattr(settings, 'openai_global_concurrency', 4)} глобально</code> ✅\n"
        f"  • Web search: <code>включен</code> 🔍\n\n"
        f"🔧 /setmodel — сменить модель\n"
        f"📊 /checkmodel — проверить модель"
    )
    
    await send_long_html_message(msg, response_text)