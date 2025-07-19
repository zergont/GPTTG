#!/bin/bash
# Скрипт для обновления кода и перезапуска бота
# Используйте: sudo ./update_bot.sh

set -e

REPO_DIR="/path/to/GPTTG"  # укажите путь к вашему проекту
SERVICE_NAME="gpttg-bot"

cd "$REPO_DIR"
echo "Обновление кода из git..."
git pull

if [ -f "pyproject.toml" ]; then
    echo "Обновление зависимостей через poetry..."
    poetry install
fi

echo "Перезапуск сервиса $SERVICE_NAME..."
sudo systemctl restart $SERVICE_NAME

echo "Статус сервиса:"
systemctl status $SERVICE_NAME --no-pager
