"""Конфигурация приложения.
Все переменные окружения читаются один раз при старте, после чего доступ к
настройкам осуществляется через `settings`, не трогая `os.environ` напрямую.
"""
from dataclasses import dataclass
import os
import sys
import platform
import subprocess
from pathlib import Path

# Определяем платформу
PLATFORM = platform.system().lower()
IS_WINDOWS = PLATFORM == 'windows'
IS_LINUX = PLATFORM == 'linux'
IS_DEVELOPMENT = os.path.exists('.git') and not os.path.exists('/etc/systemd')

# Функции для чтения версии
try:
    import toml
except ImportError:
    print("Устанавливается пакет toml для чтения версии...")
    if IS_WINDOWS:
        os.system("pip install toml")
    else:
        os.system("python3 -m pip install toml")
    import toml

def get_version_from_pyproject():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        data = toml.load(pyproject_path)
        return data.get("tool", {}).get("poetry", {}).get("version", "unknown")
    return "unknown"

# Получаем версию сразу
VERSION = get_version_from_pyproject()

# Определяем класс Settings заранее
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
    debug_mode: bool
    # Платформо-зависимые настройки
    platform: str
    is_windows: bool
    is_linux: bool
    is_development: bool

def check_system_packages():
    """Проверяет и устанавливает необходимые системные пакеты (только для Linux)."""
    if IS_WINDOWS or IS_DEVELOPMENT:
        return  # Пропускаем на Windows и в режиме разработки
    
    print("🔧 Проверка системных зависимостей...")
    
    # Проверяем необходимые утилиты
    required_tools = {
        'pgrep': 'procps',
        'ps': 'procps', 
        'git': 'git'
    }
    
    missing_packages = set()
    
    for tool, package in required_tools.items():
        try:
            result = subprocess.run(['which', tool], 
                                  capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                print(f"✅ {tool} найден")
            else:
                print(f"⚠️ {tool} не найден, добавляем {package} в список установки")
                missing_packages.add(package)
        except Exception:
            print(f"⚠️ Не удалось проверить {tool}, добавляем {package} в список установки")
            missing_packages.add(package)
    
    # Устанавливаем недостающие пакеты
    if missing_packages:
        missing_list = list(missing_packages)
        print(f"📦 Устанавливаем недостающие пакеты: {', '.join(missing_list)}")
        
        try:
            # Проверяем права суперпользователя
            if os.geteuid() != 0:
                print("⚠️ Для установки системных пакетов требуются права суперпользователя")
                print("💡 Запустите бота от имени root или установите пакеты вручную:")
                print(f"   sudo apt-get update && sudo apt-get install -y {' '.join(missing_list)}")
                return
            
            # Обновляем список пакетов
            update_result = subprocess.run(['apt-get', 'update', '-qq'], 
                                         capture_output=True, text=True, timeout=30)
            if update_result.returncode != 0:
                print(f"⚠️ Ошибка обновления списка пакетов: {update_result.stderr}")
                return
            
            # Устанавливаем пакеты
            install_result = subprocess.run(['apt-get', 'install', '-y'] + missing_list,
                                          capture_output=True, text=True, timeout=60)
            if install_result.returncode == 0:
                print("✅ Системные пакеты успешно установлены")
            else:
                print(f"⚠️ Ошибка установки пакетов: {install_result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("⚠️ Таймаут при установке пакетов")
        except Exception as e:
            print(f"⚠️ Ошибка при установке системных пакетов: {e}")
            print("💡 Установите пакеты вручную:")
            print(f"   sudo apt-get update && sudo apt-get install -y {' '.join(missing_list)}")
    else:
        print("✅ Все системные зависимости присутствуют")

# Функция для создания настроек
def create_settings():
    """Создает объект настроек после проверки всех зависимостей."""
    
    platform_info = f" ({PLATFORM}{'|dev' if IS_DEVELOPMENT else '|prod'})"
    print(f"GPTTG Telegram Bot v{VERSION}{platform_info}")

    # --- Проверка системных пакетов (только для Linux продакшен) ---
    check_system_packages()

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
        ("SYSTEM_PROMPT", "Ты — полезный ассистент."),
        ("OPENAI_PRICE_PER_1K_TOKENS", "0.002"),
        ("WHISPER_PRICE", "0.006"),
        ("DALLE_PRICE", "0.040"),
        ("MAX_FILE_MB", "20"),
        ("DEBUG_MODE", "1" if IS_DEVELOPMENT else "0"),  # Автоматически включаем debug в dev
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
        debug_mode=bool(int(env_values["DEBUG_MODE"])),
        # Платформо-зависимые настройки
        platform=PLATFORM,
        is_windows=IS_WINDOWS,
        is_linux=IS_LINUX,
        is_development=IS_DEVELOPMENT
    )

# Создаем настройки только при импорте модуля
settings = create_settings()