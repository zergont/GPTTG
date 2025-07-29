#!/bin/bash
# Скрипт для разработчиков - тестирование на локальной машине
# Кроссплатформенный запуск для Windows и Linux

set -e

echo "🔧 GPTTG Development Script"
echo "========================="

# Определяем платформу
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    PLATFORM="windows"
    PYTHON_CMD="python"
    POETRY_CMD="poetry"
else
    PLATFORM="linux"
    PYTHON_CMD="python3"
    POETRY_CMD="poetry"
fi

echo "🖥️ Платформа: $PLATFORM"

# Проверка Python
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "❌ Python не найден! Установите Python 3.9+"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
echo "🐍 Python версия: $PYTHON_VERSION"

# Проверка Poetry
if ! command -v $POETRY_CMD &> /dev/null; then
    echo "⚠️ Poetry не найден, устанавливаем..."
    if [[ "$PLATFORM" == "windows" ]]; then
        # Для Git Bash на Windows используем curl, если доступен
        if command -v curl &> /dev/null; then
            curl -sSL https://install.python-poetry.org | $PYTHON_CMD -
        else
            echo "💡 Установите Poetry вручную: https://python-poetry.org/docs/#installation"
            exit 1
        fi
    else
        curl -sSL https://install.python-poetry.org | $PYTHON_CMD -
    fi
    echo "✅ Poetry установлен"
    echo "💡 Перезапустите терминал для обновления PATH"
fi

# Создание виртуального окружения
echo "📦 Настройка окружения..."
if [ ! -d ".venv" ]; then
    echo "🔨 Создаю виртуальное окружение..."
    $POETRY_CMD install
    echo "✅ Виртуальное окружение создано"
else
    echo "🔄 Обновляю зависимости..."
    $POETRY_CMD install
    echo "✅ Зависимости обновлены"
fi

# Проверка .env файла
if [ ! -f ".env" ]; then
    echo "⚠️ Файл .env не найден!"
    if [ -f ".env.example" ]; then
        echo "📋 Копирую .env.example в .env..."
        cp .env.example .env
        echo "💡 Отредактируйте .env файл с вашими настройками"
    else
        echo "❌ Файл .env.example также не найден!"
        exit 1
    fi
else
    echo "✅ Файл .env найден"
fi

# Проверка конфигурации
echo "🧪 Тестирование конфигурации..."
$POETRY_CMD run python -c "
try:
    from bot.config import settings, VERSION
    print(f'✅ Конфигурация загружена')
    print(f'📋 Версия: {VERSION}')
    print(f'🖥️ Платформа: {settings.platform}')
    print(f'🔧 Режим разработки: {settings.is_development}')
    print(f'🔍 Debug режим: {settings.debug_mode}')
except Exception as e:
    print(f'❌ Ошибка конфигурации: {e}')
    exit(1)
"

echo ""
echo "🚀 Готово к разработке!"
echo "========================"
echo "Команды для запуска:"
echo "  $POETRY_CMD run python -m bot.main  # Запуск бота"
echo "  $POETRY_CMD shell                   # Активация окружения"
echo "  $POETRY_CMD run pytest              # Запуск тестов (если есть)"
echo ""