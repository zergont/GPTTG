"""Конфигурация приложения.
Все переменные окружения читаются один раз при старте, после чего доступ к
настройкам осуществляется через `settings`, не трогая `os.environ` напрямую.
"""
from dataclasses import dataclass
import os
import sys
from pathlib import Path

try:
    import toml
except ImportError:
    print("Устанавливается пакет toml для чтения версии...")
    os.system("pip install toml")
    import toml

def get_version_from_pyproject():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        data = toml.load(pyproject_path)
        return data.get("tool", {}).get("poetry", {}).get("version", "unknown")
    return "unknown"

VERSION = get_version_from_pyproject()
print(f"GPTTG Telegram Bot v{VERSION}")

# --- Проверка необходимых пакетов ---
REQUIRED_PACKAGES = [
    "aiogram",
    "aiohttp",
    "openai",
    "backoff",
    "python_dotenv",
    "aiosqlite",
    "toml",
    "aiocron",  # Добавлен aiocron для планировщика автообновлений
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
    print("   poetry install")
    print("   pip install " + " ".join(package_errors))
    sys.exit(1)
# --- Конец проверки пакетов ---

# Проверяем наличие .env
env_path = Path('.') / '.env'
if not env_path.exists():
    print("⚠️  Файл .env не найден в корне проекта!")
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
    ("SYSTEM_PROMPT", "Ты — полезный ассистент."),
    ("OPENAI_PRICE_PER_1K_TOKENS", "0.002"),
    ("WHISPER_PRICE", "0.006"),
    ("DALLE_PRICE", "0.040"),
    ("MAX_FILE_MB", "20"),
    ("DEBUG_MODE", "0"),
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

@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str = env_values["BOT_TOKEN"]
    openai_api_key: str = env_values["OPENAI_API_KEY"]
    admin_id: int = int(env_values["ADMIN_ID"])
    system_prompt: str = env_values["SYSTEM_PROMPT"]
    openai_price_per_1k_tokens: float = float(env_values["OPENAI_PRICE_PER_1K_TOKENS"])
    whisper_price: float = float(env_values["WHISPER_PRICE"])
    dalle_price: float = float(env_values["DALLE_PRICE"])
    max_file_mb: int = int(env_values["MAX_FILE_MB"])
    debug_mode: bool = bool(int(env_values["DEBUG_MODE"]))