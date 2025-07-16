"""Командные хендлеры: /start, /help, /img, /reset, /stats, /stat, /models, /setmodel."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

from bot.config import settings
from bot.keyboards import main_kb
from bot.utils.openai_client import OpenAIClient
from bot.utils.db import get_conn, get_user_display_name
from bot.utils.progress import show_progress_indicator

router = Router()


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
        "🤖 *Доступные команды:*",
        "",
        "💬 Просто пишите мне — я отвечу",
        "🖼 Отправьте фото с подписью — проанализирую",
        "🎤 Отправьте голосовое — распознаю и отвечу",
        "📄 Отправьте документ — прочитаю и проанализирую",  # Новая строка
        "",
        "*Команды:*",
        "/start — приветствие и информация о боте",
        "/help — эта справка",
        "/img <промпт> — сгенерировать картинку",
        "/reset — очистить историю контекста",
        "/stats — показать личные расходы",
    ]
    
    if msg.from_user.id == settings.admin_id:
        help_lines.extend([
            "",
            "*Админские команды:*",
            "/stat — общая статистика",
            "/models — показать доступные модели",
            "/setmodel — изменить текущую модель"
        ])
    
    await msg.answer("\n".join(help_lines), 
                    parse_mode="Markdown",
                    reply_markup=main_kb(msg.from_user.id == settings.admin_id))


# ——— /models (админ) —————————————————————————————————————————— #
@router.message(F.text == "/models")
async def cmd_models(msg: Message):
    """Показывает доступные модели (только для админа)."""
    if msg.from_user.id != settings.admin_id:
        return

    try:
        current_model = await OpenAIClient.get_current_model()
        models = await OpenAIClient.get_available_models()
        
        models_text = f"🤖 *Доступные модели:*\n\n"
        models_text += f"🔸 *Текущая модель:* `{current_model}`\n\n"
        
        for model in models[:10]:  # Показываем первые 10 моделей
            status = "✅" if model['id'] == current_model else "⚪"
            models_text += f"{status} `{model['id']}`\n"
        
        models_text += f"\nИспользуйте /setmodel для смены модели"
        
        await msg.answer(models_text, parse_mode="Markdown")
        
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
    """Удаляет сохранённый previous_response_id для чата."""
    async with get_conn() as db:
        await db.execute(
            "DELETE FROM chat_history WHERE chat_id = ?",
            (msg.chat.id,)
        )
        await db.commit()
    await msg.answer("🗑 История очищена! Следующий запрос начнет новый диалог.", 
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
    
    stats_text = f"📊 *Ваша статистика:*\n\n💰 Общие расходы: *${total:.4f}*\n\n"
    
    if models:
        stats_text += "*По моделям:*\n"
        for model, requests, cost in models:
            # Экранируем специальные символы для Markdown
            safe_model = model.replace("-", "\\-").replace(".", "\\.")
            stats_text += f"• {safe_model}: {requests} запросов — ${cost:.4f}\n"
    else:
        stats_text += "Пока нет данных об использовании\\."
    
    await msg.answer(stats_text, parse_mode="Markdown")


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
        # Экранируем специальные символы Markdown в именах пользователей
        safe_name = (display_name
                    .replace("_", "\\_")
                    .replace("*", "\\*")
                    .replace("[", "\\[")
                    .replace("]", "\\]")
                    .replace("(", "\\(")
                    .replace(")", "\\)")
                    .replace("~", "\\~")
                    .replace("`", "\\`")
                    .replace(">", "\\>")
                    .replace("#", "\\#")
                    .replace("+", "\\+")
                    .replace("-", "\\-")
                    .replace("=", "\\=")
                    .replace("|", "\\|")
                    .replace("{", "\\{")
                    .replace("}", "\\}")
                    .replace(".", "\\.")
                    .replace("!", "\\!"))
        leaderboard_lines.append(f"• {safe_name} — ${cost:.4f}")
    
    leaderboard = "\n".join(leaderboard_lines) or "—"

    stat_text = (
        f"📈 *Общая статистика:*\n\n"
        f"🤖 *Текущая модель:* `{current_model}`\n\n"
        f"📅 За сутки: *${day_total:.4f}*\n"
        f"📅 За неделю: *${week_total:.4f}*\n"
        f"📅 За месяц: *${month_total:.4f}*\n\n"
        f"🏆 *Топ\\-10 пользователей:*\n{leaderboard}"
    )
    await msg.answer(stat_text, parse_mode="Markdown")


# ——— /img —————————————————————————————————————————————— #
@router.message(F.text.startswith("/img"))
async def cmd_img(msg: Message):
    """Генерирует изображение через DALL·E 3."""
    progress_task = None
    try:
        prompt_part, _, size_part = msg.text.partition("|")
        # Для совместимости с Python <3.9
        if prompt_part.startswith("/img"):
            prompt = prompt_part[4:].strip()
        else:
            prompt = prompt_part.strip()
        prompt = prompt or "Смешной кот"
        size = size_part.strip() or "1024x1024"

        # Валидируем размер (DALL·E 3 поддерживает три значения)
        if size not in {"256x256", "512x512", "1024x1024"}:
            size = "1024x1024"

        # Запускаем индикатор прогресса вместо статического сообщения
        progress_task = asyncio.create_task(
            show_progress_indicator(msg.bot, msg.chat.id, max_time=60)
        )

        url = await OpenAIClient.dalle(prompt, size, msg.chat.id, msg.from_user.id)
        if not url:
            raise ValueError("Не удалось получить изображение.")
            
        await msg.answer_photo(url, caption=f"🖼 {prompt}")
        
    except Exception as e:
        await msg.answer(f"❌ Ошибка генерации изображения: {e}")
    finally:
        # Гарантированно отменяем задачу индикации
        if progress_task and not progress_task.done():
            progress_task.cancel()