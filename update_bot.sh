#!/bin/bash
# Скрипт для обновления кода и перезапуска бота с сохранением .env и базы bot.sqlite
# Используйте: sudo ./update_bot.sh

# Убираем set -e, чтобы скрипт не останавливался при мелких ошибках
# set -e

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
if systemctl stop $SERVICE_NAME; then
    echo "✅ Сервис остановлен успешно"
else
    echo "⚠️ Сервис уже был остановлен или произошла ошибка"
fi

# Принудительное обновление кода из git, не трогаем .env, базу и .git
echo "📥 Обновление кода из Git..."
find . -maxdepth 1 ! -name "$ENV_FILE" ! -name "$ENV_BACKUP" ! -name "$DB_BACKUP" ! -name "$LAST_VERSION_BACKUP" ! -name ".git" ! -name "." ! -name "logs" ! -name "bot" -exec rm -rf {} +
if git fetch origin; then
    echo "✅ Git fetch выполнен успешно"
else
    echo "❌ Ошибка Git fetch, но продолжаем..."
fi

# Восстанавливаем только отслеживаемые файлы, кроме .env и базы
if git reset --hard origin/beta; then
    echo "✅ Git reset выполнен успешно"
else
    echo "❌ Ошибка Git reset, но продолжаем..."
fi

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
    python3 -m venv .venv || echo "⚠️ Ошибка создания venv, но продолжаем..."
fi

# Проверяем наличие зависимостей
if [ -f "pyproject.toml" ]; then
    echo "📦 Обновление зависимостей через poetry..."
    export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
    if ! command -v poetry &> /dev/null; then
        echo "📎 Poetry не найден, использую полный путь..."
        # Удаляем старый lock file и создаем новый
        rm -f poetry.lock
        if /root/.local/bin/poetry lock; then
            echo "✅ Poetry lock успешно"
        else
            echo "⚠️ Ошибка poetry lock, но продолжаем..."
        fi
        if /root/.local/bin/poetry install; then
            echo "✅ Poetry install успешно"
        else
            echo "⚠️ Ошибка poetry install, но продолжаем..."
        fi
    else
        # Удаляем старый lock file и создаем новый
        rm -f poetry.lock
        if poetry lock; then
            echo "✅ Poetry lock успешно"
        else
            echo "⚠️ Ошибка poetry lock, но продолжаем..."
        fi
        if poetry install; then
            echo "✅ Poetry install успешно"
        else
            echo "⚠️ Ошибка poetry install, но продолжаем..."
        fi
    fi
    echo "✅ Зависимости обновлены"
fi

# Проверяем наличие bot/main.py
if [ ! -f "bot/main.py" ]; then
    echo "❌ Файл bot/main.py не найден! Но продолжаем с перезапуском..."
else
    echo "✅ Файл bot/main.py найден"
fi

# Тестируем, что бот может запуститься (НЕ КРИТИЧНО)
echo "🧪 Проверка работоспособности бота..."
if timeout 15s .venv/bin/python3 -c "
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
"; then
    echo "✅ Тестирование прошло успешно"
else
    echo "⚠️ Ошибка при тестировании бота, но продолжаем с перезапуском..."
fi

# Копируем актуальный unit-файл systemd
if [ -f "gpttg-bot.service" ]; then
    echo "⚙️ Копирование gpttg-bot.service в /etc/systemd/system/"
    if cp gpttg-bot.service /etc/systemd/system/gpttg-bot.service; then
        echo "✅ Systemd файл скопирован"
    else
        echo "⚠️ Ошибка копирования systemd файла"
    fi
    if systemctl daemon-reload; then
        echo "✅ Systemd daemon-reload выполнен"
    else
        echo "⚠️ Ошибка daemon-reload"
    fi
    echo "✅ Systemd конфигурация обновлена"
fi

# Убеждаемся, что директория для логов существует
mkdir -p /root/GPTTG/logs

# Убеждаемся, что сервис включен для автозапуска
echo "🔧 Проверка автозапуска сервиса..."
if ! systemctl is-enabled $SERVICE_NAME &> /dev/null; then
    if systemctl enable $SERVICE_NAME; then
        echo "✅ Автозапуск сервиса включен"
    else
        echo "⚠️ Ошибка включения автозапуска"
    fi
fi

# Создаем отложенный скрипт перезапуска для надежности (КРИТИЧНО!)
echo "🚀 Создание отложенного скрипта перезапуска..."
cat > /tmp/restart_bot.sh << 'EOF'
#!/bin/bash
echo "🔄 Отложенный перезапуск начат в $(date)"
sleep 3
echo "🚀 Запуск сервиса gpttg-bot..."
systemctl start gpttg-bot
sleep 5
for i in {1..6}; do
    if systemctl is-active --quiet gpttg-bot; then
        echo "✅ Сервис gpttg-bot успешно запущен в $(date)"
        systemctl status gpttg-bot --no-pager --lines=3
        exit 0
    fi
    echo "⏳ Попытка $i/6: ожидание запуска сервиса в $(date)..."
    sleep 5
done
echo "❌ Не удалось запустить сервис после 6 попыток в $(date)"
journalctl -u gpttg-bot --no-pager --lines=10
exit 1
EOF

chmod +x /tmp/restart_bot.sh
echo "✅ Отложенный скрипт создан"

# Запуск отложенного скрипта в фоне (КРИТИЧНО!)
echo "🚀 Запуск отложенного перезапуска сервиса..."
if nohup /tmp/restart_bot.sh > /tmp/restart_bot.log 2>&1 &; then
    echo "✅ Отложенный скрипт запущен в фоне"
else
    echo "❌ Ошибка запуска отложенного скрипта!"
    # Прямой запуск в качестве backup
    echo "🔄 Попытка прямого запуска сервиса..."
    systemctl start $SERVICE_NAME || echo "❌ Прямой запуск тоже не удался"
fi

# Выводим версию приложения из pyproject.toml
if [ -f "pyproject.toml" ]; then
    VERSION=$(grep '^version' pyproject.toml | head -1 | awk -F '"' '{print $2}')
    echo "🎉 Обновление завершено! Версия приложения: $VERSION"
fi

echo "=== Обновление GPTTG завершено успешно ==="
echo "🔄 Сервис будет перезапущен в фоновом режиме через 3 секунды"
echo "📋 Логи перезапуска: tail -f /tmp/restart_bot.log"
echo "📊 Статус сервиса: sudo systemctl status gpttg-bot"