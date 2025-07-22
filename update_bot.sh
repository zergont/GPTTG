#!/bin/bash
# Скрипт для обновления кода и перезапуска бота с сохранением .env и базы bot.sqlite
# Используйте: sudo ./update_bot.sh

set -e

REPO_DIR="/root/GPTTG"  # путь к вашему проекту
SERVICE_NAME="gpttg-bot"
GIT_REPO="https://github.com/zergont/GPTTG.git"
ENV_FILE=".env"
ENV_BACKUP=".env.backup"
DB_FILE="bot.sqlite"
DB_BACKUP="bot.sqlite.backup"
LAST_VERSION_FILE="last_version.txt"
LAST_VERSION_BACKUP="last_version.txt.backup"

cd "$REPO_DIR"

# Сохраняем .env, базу и last_version.txt перед обновлением
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$ENV_BACKUP"
    echo "Файл .env сохранён в .env.backup"
fi
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$DB_BACKUP"
    echo "База bot.sqlite сохранена в bot.sqlite.backup"
fi
if [ -f "$LAST_VERSION_FILE" ]; then
    cp "$LAST_VERSION_FILE" "$LAST_VERSION_BACKUP"
    echo "Файл last_version.txt сохранён в last_version.txt.backup"
fi

# Принудительное обновление кода из git, не трогаем .env, базу и .git
find . -maxdepth 1 ! -name "$ENV_FILE" ! -name "$ENV_BACKUP" ! -name "$DB_FILE" ! -name "$DB_BACKUP" ! -name "$LAST_VERSION_FILE" ! -name "$LAST_VERSION_BACKUP" ! -name ".git" ! -name "." -exec rm -rf {} +
git fetch origin
# Восстанавливаем только отслеживаемые файлы, кроме .env и базы
git reset --hard origin/beta

echo "Восстанавливаем .env, базу и last_version.txt после обновления..."
if [ -f "$ENV_BACKUP" ]; then
    mv "$ENV_BACKUP" "$ENV_FILE"
    echo ".env восстановлен."
fi
if [ -f "$DB_BACKUP" ]; then
    mv "$DB_BACKUP" "$DB_FILE"
    echo "bot.sqlite восстановлен."
fi
if [ -f "$LAST_VERSION_BACKUP" ]; then
    mv "$LAST_VERSION_BACKUP" "$LAST_VERSION_FILE"
    echo "last_version.txt восстановлен."
fi

# Проверяем наличие виртуального окружения и python3
if [ ! -f ".venv/bin/python3" ]; then
    echo "Виртуальное окружение не найдено, создаю..."
    python3 -m venv .venv
fi

# Проверяем наличие зависимостей
if [ -f "pyproject.toml" ]; then
    echo "Обновление зависимостей через poetry..."
    export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
    if ! command -v poetry &> /dev/null; then
        echo "Poetry не найден, использую полный путь..."
        # Удаляем старый lock file и создаем новый
        rm -f poetry.lock
        /root/.local/bin/poetry lock
        /root/.local/bin/poetry install
    else
        # Удаляем старый lock file и создаем новый
        rm -f poetry.lock
        poetry lock
        poetry install
    fi
fi

# Проверяем наличие bot/main.py
if [ ! -f "bot/main.py" ]; then
    echo "Файл bot/main.py не найден! Обновление прервано."
    exit 1
fi

# Копируем актуальный unit-файл systemd
if [ -f "gpttg-bot.service" ]; then
    echo "Копирование gpttg-bot.service в /etc/systemd/system/"
    cp gpttg-bot.service /etc/systemd/system/gpttg-bot.service
    systemctl daemon-reload
fi

# Создаём директорию для логов, если её нет
mkdir -p /root/GPTTG/logs

# Перезапуск сервиса
echo "Перезапуск сервиса $SERVICE_NAME..."
systemctl restart $SERVICE_NAME

echo "Статус сервиса:"
systemctl status $SERVICE_NAME --no-pager

# Выводим версию приложения из pyproject.toml
if [ -f "pyproject.toml" ]; then
    VERSION=$(grep '^version' pyproject.toml | head -1 | awk -F '"' '{print $2}')
    echo "Версия приложения: $VERSION"
fi