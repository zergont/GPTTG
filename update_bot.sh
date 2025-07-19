#!/bin/bash
# Скрипт для обновления кода и перезапуска бота
# Используйте: sudo ./update_bot.sh

set -e

REPO_DIR="/root/GPTTG"  # путь к вашему проекту
SERVICE_NAME="gpttg-bot"
GIT_REPO="https://github.com/zergont/GPTTG.git"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Клонируем репозиторий..."
    git clone "$GIT_REPO" "$REPO_DIR"
fi

cd "$REPO_DIR"
echo "Обновление кода из git..."
git pull

if [ -f "pyproject.toml" ]; then
    echo "Обновление зависимостей через poetry..."
    poetry install
fi

echo "Перезапуск сервиса $SERVICE_NAME..."
systemctl restart $SERVICE_NAME

echo "Статус сервиса:"
systemctl status $SERVICE_NAME --no-pager
