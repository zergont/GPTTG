#!/bin/bash
# Упрощённый скрипт обновления GPTTG
# Используйте: sudo ./update_bot.sh

set -e

REPO_DIR="/root/GPTTG"
SERVICE_NAME="gpttg-bot"

cd "$REPO_DIR"

echo "=== Начало обновления GPTTG ==="

# Проверяем права суперпользователя
if [[ $EUID -ne 0 ]]; then
   echo "❌ Этот скрипт должен быть запущен от имени root"
   exit 1
fi

# Сохраняем важные файлы
echo "💾 Сохранение конфигурации и данных..."
cp .env .env.backup 2>/dev/null || echo "⚠️ Файл .env не найден"
cp bot/bot.sqlite bot.sqlite.backup 2>/dev/null || echo "⚠️ База данных не найдена"
cp last_version.txt last_version.backup 2>/dev/null || echo "⚠️ Файл версии не найден"

# Останавливаем сервис
echo "🛑 Остановка сервиса $SERVICE_NAME..."
systemctl stop $SERVICE_NAME || echo "⚠️ Сервис уже остановлен"

# Обновляем код
echo "📥 Обновление кода из Git..."
git fetch origin
git reset --hard origin/beta

# Восстанавливаем сохранённые файлы
echo "🔄 Восстановление конфигурации..."
mv .env.backup .env 2>/dev/null || echo "⚠️ Не удалось восстановить .env"
mv bot.sqlite.backup bot/bot.sqlite 2>/dev/null || echo "⚠️ Не удалось восстановить базу"
mv last_version.backup last_version.txt 2>/dev/null || echo "⚠️ Не удалось восстановить версию"

# Обновляем зависимости
echo "📦 Обновление зависимостей..."
export PATH="$HOME/.local/bin:$PATH"
if command -v poetry &> /dev/null; then
    poetry install --only=main
else
    echo "⚠️ Poetry не найден, используем pip"
    pip install -r requirements.txt
fi

# Обновляем systemd сервис
if [ -f "gpttg-bot.service" ]; then
    echo "⚙️ Обновление systemd сервиса..."
    cp gpttg-bot.service /etc/systemd/system/
    systemctl daemon-reload
fi

# Запускаем сервис
echo "🚀 Запуск сервиса $SERVICE_NAME..."
systemctl start $SERVICE_NAME

# Проверяем статус
echo "⏳ Ожидание запуска..."
sleep 5

for i in {1..6}; do
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✅ Сервис успешно запущен!"
        systemctl status $SERVICE_NAME --no-pager --lines=3
        
        # Получаем версию из pyproject.toml
        if [ -f "pyproject.toml" ]; then
            VERSION=$(grep '^version' pyproject.toml | head -1 | awk -F '"' '{print $2}')
            echo "🎉 Обновление завершено! Версия: $VERSION"
        fi
        
        echo "=== Обновление GPTTG завершено успешно ==="
        exit 0
    fi
    echo "⏳ Попытка $i/6: ожидание запуска..."
    sleep 5
done

echo "❌ Не удалось запустить сервис"
systemctl status $SERVICE_NAME --no-pager
journalctl -u $SERVICE_NAME --no-pager --lines=10
exit 1