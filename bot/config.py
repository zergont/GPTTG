"""Конфигурация приложения.
Все переменные окружения читаются один раз при старте, после чего доступ к
настройкам осуществляется через `settings`, не трогая `os.environ` напрямую.
"""
from dataclasses import dataclass
import os
import sys
from pathlib import Path

# --- Проверка необходимых пакетов ---
REQUIRED_PACKAGES = [
    "aiogram",
    "aiohttp",
    "openai",
    "backoff",
    "python_dotenv",
    "aiosqlite",  # добавить эту строку
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

def _env(name: str, default: str | None = None) -> str:
    """Возвращает значение переменной окружения или бросает ошибку."""
    val = os.getenv(name, default)
    if val is None:
        print(f"❌ Не удалось считать обязательную переменную {name}")
        raise RuntimeError(f"Не задана обязательная переменная {name}")
    print(f"✅ Переменная {name} успешно считана")
    return val

# Проверка переменных окружения с остановкой при ошибке
REQUIRED_ENV_VARS = [
    "BOT_TOKEN",
    "OPENAI_API_KEY",
    "ADMIN_ID",
]

env_errors = []
for var in REQUIRED_ENV_VARS:
    try:
        _env(var)
    except RuntimeError:
        env_errors.append(var)
if env_errors:
    print(f"\n❌ Не заданы обязательные переменные окружения: {', '.join(env_errors)}")
    sys.exit(1)

@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str = _env("BOT_TOKEN")
    openai_api_key: str = _env("OPENAI_API_KEY")
    admin_id: int = int(_env("ADMIN_ID"))
    system_prompt: str = _env("SYSTEM_PROMPT", "Ты — полезный ассистент.")
    openai_price_per_1k_tokens: float = float(_env("OPENAI_PRICE_PER_1K_TOKENS", "0.002"))
    whisper_price: float = float(_env("WHISPER_PRICE", "0.006"))
    dalle_price: float = float(_env("DALLE_PRICE", "0.040"))
    max_file_mb: int = int(_env("MAX_FILE_MB", "20"))  # Максимальный размер файла в МБ
    debug_mode: bool = bool(int(_env("DEBUG_MODE", "0")))  # <-- добавить эту строку

# Создаем экземпляр настроек
settings = Settings()