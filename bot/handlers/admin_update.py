import asyncio
from aiogram import Router, F, types

ADMIN_ID = 407281873          # ваш ID администратора

router = Router(name="admin_update")

@router.message(F.text.casefold() == "/update")
async def cmd_update(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return  # игнорируем остальных
    await message.answer("⚙️ Обновляюсь…")
    # запускаем скрипт без немедленного рестарта
    proc = await asyncio.create_subprocess_exec(
        "sudo", "/usr/bin/chmod +x /root/GPTTG/update_bot.sh && /root/GPTTG/update_bot.sh", "--no-restart",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    # показываем последние 1.5 кБ лога
    snippet = out.decode(errors="ignore")[-1500:] or "(вывод пуст)"
    await message.answer(
        f"✅ Обновление завершено:\n<pre>{snippet}</pre>",
        parse_mode="HTML",
    )
