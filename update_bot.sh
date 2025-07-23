#!/bin/bash
# Скрипт для обновления кода и перезапуска бота с сохранением .env и базы bot.sqlite
# Используйте: sudo ./update_bot.sh

set -e

REPO_DIR="/root/GPTTG"  # путь к вашему проекту
SERVICE_NAME="gpttg-bot"
GIT_REPO="https://github.com/zergont/GPTTG.git"
ENV_FILE=".env"
ENV_BACKUP=".env.backup"
DB_FILE="bot/bot.sqlite"  # ИСПРАВЛЕНО: база находится в папке bot/
DB_BACKUP="bot.sqlite.backup"
LAST_VERSION_FILE="last_version.txt"
LAST_VERSION_BACKUP="last_version.txt.backup"

cd "$REPO_DIR"

echo "=== Начало обновления GPTTG ==="

# Создаём директорию для логов сразу
echo "📁 Создание директории для логов..."
mkdir -p /root/GPTTG/logs
echo "✅ Директория logs создана"

# Сохраняем .env, базу и last_version.txt перед обновлением
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$ENV_BACKUP"
    echo "✅ Файл .env сохранён в .env.backup"
fi
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$DB_BACKUP"
    echo "✅ База bot.sqlite сохранена в bot.sqlite.backup"
fi
if [ -f "$LAST_VERSION_FILE" ]; then
    cp "$LAST_VERSION_FILE" "$LAST_VERSION_BACKUP"
    echo "✅ Файл last_version.txt сохранён в last_version.txt.backup"
fi

# Остановка сервиса перед обновлением
echo "🛑 Остановка сервиса $SERVICE_NAME..."
systemctl stop $SERVICE_NAME || true

# Принудительное обновление кода из git, не трогаем .env, базу и .git
echo "📥 Обновление кода из Git..."
find . -maxdepth 1 ! -name "$ENV_FILE" ! -name "$ENV_BACKUP" ! -name "$DB_BACKUP" ! -name "$LAST_VERSION_BACKUP" ! -name ".git" ! -name "." ! -name "logs" ! -name "bot" -exec rm -rf {} +
git fetch origin
# Восстанавливаем только отслеживаемые файлы, кроме .env и базы
git reset --hard origin/beta

echo "🔄 Восстанавливаем .env, базу и last_version.txt после обновления..."
if [ -f "$ENV_BACKUP" ]; then
    mv "$ENV_BACKUP" "$ENV_FILE"
    echo "✅ .env восстановлен."
fi
if [ -f "$DB_BACKUP" ]; then
    mv "$DB_BACKUP" "$DB_FILE"
    echo "✅ bot.sqlite восстановлен."
fi
if [ -f "$LAST_VERSION_BACKUP" ]; then
    mv "$LAST_VERSION_BACKUP" "$LAST_VERSION_FILE"
    echo "✅ last_version.txt восстановлен."
fi

# Проверяем наличие виртуального окружения и python3
if [ ! -f ".venv/bin/python3" ]; then
    echo "🐍 Виртуальное окружение не найдено, создаю..."
    python3 -m venv .venv
fi

# Проверяем наличие зависимостей
if [ -f "pyproject.toml" ]; then
    echo "📦 Обновление зависимостей через poetry..."
    export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
    if ! command -v poetry &> /dev/null; then
        echo "📎 Poetry не найден, использую полный путь..."
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
    echo "✅ Зависимости обновлены"
fi

# Проверяем наличие bot/main.py
if [ ! -f "bot/main.py" ]; then
    echo "❌ Файл bot/main.py не найден! Обновление прервано."
    exit 1
fi

# Тестируем, что бот может запуститься
echo "🧪 Проверка работоспособности бота..."
timeout 15s .venv/bin/python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from bot.config import settings, VERSION
    print(f'✅ Конфигурация загружена, версия: {VERSION}')
    print(f'✅ Bot token: {\"✓\" if settings.bot_token else \"✗\"}')
    print(f'✅ OpenAI API key: {\"✓\" if settings.openai_api_key else \"✗\"}')
    print(f'✅ Admin ID: {settings.admin_id}')
    print(f'✅ Платформа: {settings.platform} ({\"dev\" if settings.is_development else \"prod\"})')
except Exception as e:
    print(f'❌ Ошибка загрузки конфигурации: {e}')
    sys.exit(1)
" || {
    echo "❌ Ошибка при тестировании бота!"
    echo "🔍 Проверяем логи зависимостей:"
    .venv/bin/python3 -c "import bot.config" 2>&1 || true
    exit 1
}

# Копируем актуальный unit-файл systemd
if [ -f "gpttg-bot.service" ]; then
    echo "⚙️ Копирование gpttg-bot.service в /etc/systemd/system/"
    cp gpttg-bot.service /etc/systemd/system/gpttg-bot.service
    systemctl daemon-reload
    echo "✅ Systemd конфигурация обновлена"
fi

# Убеждаемся, что директория для логов существует
mkdir -p /root/GPTTG/logs

# Убеждаемся, что сервис включен для автозапуска
echo "🔧 Проверка автозапуска сервиса..."
if ! systemctl is-enabled $SERVICE_NAME &> /dev/null; then
    systemctl enable $SERVICE_NAME
    echo "✅ Автозапуск сервиса включен"
fi

# Создаем отложенный скрипт перезапуска для надежности
echo "🚀 Создание отложенного скрипта перезапуска..."
cat > /tmp/restart_bot.sh << 'EOF'
#!/bin/bash
sleep 3
systemctl start gpttg-bot
sleep 5
for i in {1..6}; do
    if systemctl is-active --quiet gpttg-bot; then
        echo "✅ Сервис gpttg-bot успешно запущен"
        systemctl status gpttg-bot --no-pager --lines=3
        exit 0
    fi
    echo "⏳ Попытка $i/6: ожидание запуска сервиса..."
    sleep 5
done
echo "❌ Не удалось запустить сервис после 6 попыток"
journalctl -u gpttg-bot --no-pager --lines=10
exit 1
EOF

chmod +x /tmp/restart_bot.sh

# Запуск отложенного скрипта в фоне
echo "🚀 Запуск отложенного перезапуска сервиса..."
nohup /tmp/restart_bot.sh > /tmp/restart_bot.log 2>&1 &

# Выводим версию приложения из pyproject.toml
if [ -f "pyproject.toml" ]; then
    VERSION=$(grep '^version' pyproject.toml | head -1 | awk -F '"' '{print $2}')
    echo "🎉 Обновление завершено! Версия приложения: $VERSION"
fi

echo "=== Обновление GPTTG завершено успешно ==="
echo "🔄 Сервис будет перезапущен в фоновом режиме через 3 секунды"
echo "📋 Логи перезапуска: tail -f /tmp/restart_bot.log"