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

cd "$REPO_DIR"

# Сохраняем .env и базу перед обновлением
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$ENV_BACKUP"
    echo "Файл .env сохранён в .env.backup"
fi
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$DB_BACKUP"
    echo "База bot.sqlite сохранена в bot.sqlite.backup"
fi

# Принудительное обновление кода из git, не трогаем .env, базу и .git
find . -maxdepth 1 ! -name "$ENV_FILE" ! -name "$ENV_BACKUP" ! -name "$DB_FILE" ! -name "$DB_BACKUP" ! -name ".git" ! -name "." -exec rm -rf {} +
git fetch origin
# Восстанавливаем только отслеживаемые файлы, кроме .env и базы
git reset --hard origin/beta

echo "Восстанавливаем .env и базу после обновления..."
if [ -f "$ENV_BACKUP" ]; then
    mv "$ENV_BACKUP" "$ENV_FILE"
    echo ".env восстановлен."
fi
if [ -f "$DB_BACKUP" ]; then
    mv "$DB_BACKUP" "$DB_FILE"
    echo "bot.sqlite восстановлен."
fi

if [ -f "pyproject.toml" ]; then
    echo "Обновление зависимостей через poetry..."
    poetry install
fi

echo "Перезапуск сервиса $SERVICE_NAME..."
systemctl restart $SERVICE_NAME

echo "Статус сервиса:"
systemctl status $SERVICE_NAME --no-pager

# Выводим версию приложения из pyproject.toml
if [ -f "pyproject.toml" ]; then
    VERSION=$(grep '^version' pyproject.toml | head -1 | awk -F '"' '{print $2}')
    echo "Версия приложения: $VERSION"
fi