"""Централизованные промпты для ассистента."""
from __future__ import annotations

from bot.config import settings


def timezone_intro() -> str:
    return (
        "По умолчанию предполагай часовой пояс пользователя Europe/Moscow. "
        "Если видишь в диалоге явные признаки другого пояса (город, текущее время, GMT±X) — уточни и установи через tool set_timezone. "
        "Спрашивай про город или текущее время только один раз при первом общении, не злоупотребляй напоминаниями."
    )


def reminder_tools_instr_long() -> str:
    return (
        "\n\nНапоминания: используй function-tool 'schedule_reminder' с полями "
        "when (ISO8601 с TZ или 'in 5m/2h/1d'), text (до 200 символов), silent (true/false). "
        "Для последовательных цепочек добавь опциональный объект chain: {next_offset_seconds:int, next_at:'YYYY-MM-DD HH:MM:SS', steps:int, end_at:'YYYY-MM-DD HH:MM:SS', silent?:bool}. "
        "Выбор инструментов — автоматический (tool_choice=auto): модель сама решает, когда вызывать функцию, а когда ответить текстом. "
        "Если пользователь просит несколько напоминаний, вызови schedule_reminder несколько раз в одном ответе первого шага (пакетом) или используй пакетный инструмент. "
        "Создавай разумное количество напоминаний и не спамь пользователя; при неопределённости уточни детали. "
        "Не отправляй отдельные сообщения-подтверждения — бот покажет итоговые подтверждения самостоятельно."
    )


def reminder_tools_instr_short() -> str:
    return " Для напоминаний используй schedule_reminder/schedule_reminders."


def self_call_instr_long() -> str:
    return (
        "\n\nЭто автономное сообщение ассистента (самовызов). Сформируй одно короткое понятное сообщение для пользователя. "
        "Если уместно продолжение позже, добавь в самом конце сообщения JSON‑маркер в HTML‑комментарии: \n"
        "<!--self_call:{\"in\":\"in 30m\",\"topic\":\"<тема>\",\"payload\":{...}}--> или <!--self_call:{\"at\":\"YYYY-MM-DD HH:MM:SS\",\"topic\":\"...\"}-->. "
        "Не добавляй никакого текста после комментария."
    )


def self_call_instr_short() -> str:
    return (
        " Это автономное сообщение ассистента. Если нужно продолжение, добавь в конце <!--self_call:{...}-->."
    )


def build_initial_system_prompt(include_reminder_tools: bool) -> str:
    base = settings.system_prompt
    tz = timezone_intro()
    extra = reminder_tools_instr_long() if include_reminder_tools else self_call_instr_long()
    return f"{base}\n\n{tz}{extra}"


def build_per_request_system_prompt(include_reminder_tools: bool) -> str:
    tz = timezone_intro()
    extra = reminder_tools_instr_short() if include_reminder_tools else self_call_instr_short()
    return f"{tz}{extra}"
