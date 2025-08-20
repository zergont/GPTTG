"""Конфигурация приложения."""
from dataclasses import dataclass
import os
import sys
import re
from pathlib import Path


def get_version_from_pyproject():
    """Читает версию из pyproject.toml без toml пакета."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        return "unknown"

    try:
        content = pyproject_path.read_text(encoding='utf-8')
        # Улучшенная регулярка для более точного поиска
        match = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return match.group(1) if match else "unknown"
    except Exception:
        return "unknown"

# Получаем версию сразу
VERSION = get_version_from_pyproject()

# Определяем платформу локально
import platform
_platform = platform.system().lower()
IS_WINDOWS = _platform == 'windows'
IS_LINUX = _platform == 'linux'
IS_DEVELOPMENT = os.path.exists('.git') and not os.path.exists('/etc/systemd')


def _parse_duration_to_seconds(val: str, default_seconds: int) -> int:
    """Парсит длительность вида '10s', '2m', '1h' в секунды. Поддерживаются s/m/h.
    Если парсинг не удался — возвращает default_seconds.
    """
    try:
        s = (val or "").strip().lower()
        if not s:
            return default_seconds
        # Если чисто число — считаем секундами
        if s.isdigit():
            return int(s)
        m = re.match(r"^(\d+)\s*([smh])$", s)
        if not m:
            return default_seconds
        num = int(m.group(1))
        unit = m.group(2)
        if unit == 's':
            return num
        if unit == 'm':
            return num * 60
        if unit == 'h':
            return num * 3600
        return default_seconds
    except Exception:
        return default_seconds


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    openai_api_key: str
    admin_id: int
    system_prompt: str
    openai_price_per_1k_tokens: float
    whisper_price: float
    dalle_price: float
    max_file_mb: int
    max_log_mb: int
    debug_mode: bool
    # Платформо-зависимые настройки
    platform: str
    is_windows: bool
    is_linux: bool
    is_development: bool
    # Новые настройки OpenAI
    openai_timeout_seconds: int
    openai_max_retries: int
    openai_global_concurrency: int
    # Напоминания
    reminder_poll_interval_seconds: int
    reminder_batch_limit: int
    reminder_lookahead_seconds: int
    reminder_jitter_seconds: int
    reminder_default_silent: bool


def create_settings():
    """Создает объект настроек после проверки всех зависимостей."""

    platform_info = f" ({_platform}{'|dev' if IS_DEVELOPMENT else '|prod'})"
    print(f"GPTTG Telegram Bot v{VERSION}{platform_info}")

    # --- Проверка необходимых пакетов ---
    REQUIRED_PACKAGES = [
        "aiogram",
        "aiohttp",
        "openai",
        "backoff",
        "python_dotenv",
        "aiosqlite",
    ]

    def check_packages():
        print("Проверка необходимых пакетов:")
        errors = []
        for pkg in REQUIRED_PACKAGES:
            try:
                if pkg == "python_dotenv":
                    __import__("dotenv")
                else:
                    __import__(pkg)
                print(f"✅ {pkg} установлен")
            except ImportError:
                print(f"❌ {pkg} не установлен")
                errors.append(pkg)
        return errors

    package_errors = check_packages()
    if package_errors:
        print(f"\n❌ Не установлены обязательные пакеты: {', '.join(package_errors)}")
        print("💡 Попробуйте выполнить одну из команд:")
        if IS_WINDOWS:
            print("   poetry install")
            print("   pip install " + " ".join(package_errors))
        else:
            print("   poetry install")
            print("   python3 -m pip install " + " ".join(package_errors))
        sys.exit(1)

    # Проверяем наличие .env
    env_path = Path('.') / '.env'
    if not env_path.exists():
        print("⚠️  Файл .env не найден в корне проекта!")
        if IS_DEVELOPMENT:
            print("💡 Создайте .env файл на основе .env.example")
    else:
        print("✅ Файл .env найден.")

    # Загружаем переменные окружения из .env
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
        print("✅ Переменные окружения из .env загружены.")
    except ImportError:
        print("⚠️  Модуль python-dotenv не установлен. Переменные окружения из .env не будут загружены.")
        sys.exit(1)

    def _env(name: str, default: str | None = None, env_dict: dict | None = None) -> str:
        """Возвращает значение переменной окружения или бросает ошибку."""
        if env_dict is not None and name in env_dict:
            val = env_dict[name]
        else:
            val = os.getenv(name, default)
        if val is None:
            print(f"❌ Не удалось считать обязательную переменную {name}")
            raise RuntimeError(f"Не задана обязательная переменная {name}")
        # Не выводим значения ключей
        if name.lower() in {"bot_token", "openai_api_key"}:
            print(f"✅ Переменная {name} успешно считана (скрыто)")
        else:
            print(f"✅ Переменная {name} = {val}")
        return val

    # --- Оптимизированная загрузка переменных окружения ---
    REQUIRED_ENV_VARS = [
        "BOT_TOKEN",
        "OPENAI_API_KEY",
        "ADMIN_ID",
    ]
    OPTIONAL_ENV_VARS = [
        ("SYSTEM_PROMPT", "Ты — полезный ассистент. У тебя есть доступ к текущему времени и дате, которые передаются в каждом сообщении пользователя."),
        ("OPENAI_PRICE_PER_1K_TOKENS", "0.002"),
        ("WHISPER_PRICE", "0.006"),
        ("DALLE_PRICE", "0.040"),
        ("MAX_FILE_MB", "20"),
        ("MAX_LOG_MB", "5"),
        ("DEBUG_MODE", "1" if IS_DEVELOPMENT else "0"),
        ("OPENAI_TIMEOUT_SECONDS", "180"),
        ("OPENAI_MAX_RETRIES", "0"),
        ("OPENAI_GLOBAL_CONCURRENCY", "4"),
        # Напоминания
        ("REMINDER_POLL_INTERVAL", "10s"),
        ("REMINDER_BATCH_LIMIT", "50"),
        ("REMINDER_LOOKAHEAD", "2s"),
        ("REMINDER_JITTER", "2s"),
        ("REMINDER_DEFAULT_SILENT", "1"),
    ]

    env_values = {}
    env_errors = []
    for var in REQUIRED_ENV_VARS:
        try:
            env_values[var] = _env(var)
        except RuntimeError:
            env_errors.append(var)
    for var, default in OPTIONAL_ENV_VARS:
        try:
            env_values[var] = _env(var, default)
        except RuntimeError:
            env_values[var] = default
    if env_errors:
        print(f"\n❌ Не заданы обязательные переменные окружения: {', '.join(env_errors)}")
        sys.exit(1)

    # Создаем объект настроек
    return Settings(
        bot_token=env_values["BOT_TOKEN"],
        openai_api_key=env_values["OPENAI_API_KEY"],
        admin_id=int(env_values["ADMIN_ID"]),
        system_prompt=env_values["SYSTEM_PROMPT"],
        openai_price_per_1k_tokens=float(env_values["OPENAI_PRICE_PER_1K_TOKENS"]),
        whisper_price=float(env_values["WHISPER_PRICE"]),
        dalle_price=float(env_values["DALLE_PRICE"]),
        max_file_mb=int(env_values["MAX_FILE_MB"]),
        max_log_mb=int(env_values["MAX_LOG_MB"]),
        debug_mode=bool(int(env_values["DEBUG_MODE"])),
        # Платформо-зависимые настройки
        platform=_platform,
        is_windows=IS_WINDOWS,
        is_linux=IS_LINUX,
        is_development=IS_DEVELOPMENT,
        # Новые настройки OpenAI
        openai_timeout_seconds=int(env_values["OPENAI_TIMEOUT_SECONDS"]),
        openai_max_retries=int(env_values["OPENAI_MAX_RETRIES"]),
        openai_global_concurrency=int(env_values["OPENAI_GLOBAL_CONCURRENCY"]),
        # Напоминания
        reminder_poll_interval_seconds=_parse_duration_to_seconds(env_values["REMINDER_POLL_INTERVAL"], 10),
        reminder_batch_limit=int(env_values["REMINDER_BATCH_LIMIT"]),
        reminder_lookahead_seconds=_parse_duration_to_seconds(env_values["REMINDER_LOOKAHEAD"], 2),
        reminder_jitter_seconds=_parse_duration_to_seconds(env_values["REMINDER_JITTER"], 2),
        reminder_default_silent=bool(int(env_values["REMINDER_DEFAULT_SILENT"])),
    )

# Создаем настройки только при импорте модуля
settings = create_settings()