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
cp .env .env.backup 2>/dev/null && echo "✅ .env сохранён" || echo "⚠️ Файл .env не найден"
cp bot/bot.sqlite bot.sqlite.backup 2>/dev/null && echo "✅ База сохранена" || echo "⚠️ База данных не найдена"
cp last_version.txt last_version.backup 2>/dev/null && echo "✅ Версия сохранена" || echo "⚠️ Файл версии не найден"

# Останавливаем сервис
echo "🛑 Остановка сервиса $SERVICE_NAME..."
if systemctl stop $SERVICE_NAME; then
    echo "✅ Сервис остановлен"
else
    echo "⚠️ Сервис уже был остановлен"
fi

# Обновляем код
echo "📥 Обновление кода из Git..."
if git fetch origin; then
    echo "✅ git fetch выполнен"
else
    echo "❌ Ошибка git fetch"
    exit 1
fi

if git reset --hard origin/beta; then
    echo "✅ git reset выполнен"
else
    echo "❌ Ошибка git reset"
    exit 1
fi

# Восстанавливаем сохранённые файлы
echo "🔄 Восстановление конфигурации..."
mv .env.backup .env 2>/dev/null && echo "✅ .env восстановлен" || echo "⚠️ Не удалось восстановить .env"
mv bot.sqlite.backup bot/bot.sqlite 2>/dev/null && echo "✅ База восстановлена" || echo "⚠️ Не удалось восстановить базу"
mv last_version.backup last_version.txt 2>/dev/null && echo "✅ Версия восстановлена" || echo "⚠️ Не удалось восстановить версию"

# Обновляем зависимости
echo "📦 Обновление зависимостей..."
export PATH="$HOME/.local/bin:$PATH"

if command -v poetry &> /dev/null; then
    echo "🔧 Используем Poetry..."
    if poetry install --only=main; then
        echo "✅ Poetry install успешно"
    else
        echo "⚠️ Ошибка poetry install, пробуем pip"
        pip install -r requirements.txt
    fi
else
    echo "🔧 Poetry не найден, используем pip..."
    pip install -r requirements.txt
fi

# Обновляем systemd сервис
if [ -f "gpttg-bot.service" ]; then
    echo "⚙️ Обновление systemd сервиса..."
    cp gpttg-bot.service /etc/systemd/system/
    systemctl daemon-reload
    echo "✅ Systemd сервис обновлён"
fi

# Запускаем сервис
echo "🚀 Запуск сервиса $SERVICE_NAME..."
if systemctl start $SERVICE_NAME; then
    echo "✅ Команда запуска выполнена"
else
    echo "❌ Ошибка команды запуска"
    exit 1
fi

# Расширенная проверка статуса
echo "⏳ Ожидание запуска сервиса (до 30 секунд)..."
for i in {1..15}; do
    sleep 2
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✅ Сервис запущен успешно! Попытка $i/15"
        systemctl status $SERVICE_NAME --no-pager --lines=3
        
        # Получаем версию из pyproject.toml
        if [ -f "pyproject.toml" ]; then
            VERSION=$(grep '^version' pyproject.toml | head -1 | awk -F '"' '{print $2}')
            echo "🎉 Обновление завершено! Версия: $VERSION"
        fi
        
        echo "=== Обновление GPTTG завершено успешно ==="
        exit 0
    else
        echo "⏳ Попытка $i/15: ожидание запуска..."
    fi
done

# Если сервис не запустился
echo "❌ Сервис не запустился за 30 секунд"
echo "📋 Подробный статус сервиса:"
systemctl status $SERVICE_NAME --no-pager
echo ""
echo "📋 Последние 15 строк логов:"
journalctl -u $SERVICE_NAME --no-pager --lines=15
echo ""
echo "📋 Проверка файлов:"
echo "- Рабочая директория: $(pwd)"
echo "- .env существует: $([ -f .env ] && echo 'да' || echo 'нет')"
echo "- bot/main.py существует: $([ -f bot/main.py ] && echo 'да' || echo 'нет')"
echo "- .venv/bin/python3 существует: $([ -f .venv/bin/python3 ] && echo 'да' || echo 'нет')"
echo ""
echo "🔧 Попробуйте перезапустить вручную:"
echo "   sudo systemctl start $SERVICE_NAME"
echo "   sudo systemctl status $SERVICE_NAME"
echo "   sudo journalctl -u $SERVICE_NAME -f"

exit 1