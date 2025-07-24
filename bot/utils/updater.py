"""Простой модуль автообновления бота."""
import asyncio
import aiohttp
import subprocess
import os
from pathlib import Path
from typing import Optional

from bot.config import settings, VERSION
from bot.utils.log import logger


class SimpleUpdater:
    """Упрощённая система автообновления."""
    
    UPDATE_SCRIPT_PATH = "/tmp/simple_update.sh"
    
    @staticmethod
    async def check_remote_version() -> Optional[str]:
        """Проверяет версию на GitHub."""
        try:
            url = "https://raw.githubusercontent.com/zergont/GPTTG/master/pyproject.toml"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return None
                    text = await resp.text()
                    
            for line in text.splitlines():
                if line.strip().startswith("version"):
                    version = line.split("=")[1].strip().strip('"')
                    return version
        except Exception as e:
            logger.error(f"Ошибка проверки версии: {e}")
        return None
    
    @staticmethod
    def create_update_script() -> bool:
        """Создаёт простой скрипт обновления."""
        script_content = f"""#!/bin/bash
# Простой скрипт автообновления GPTTG
# Логирование всех операций
exec > /tmp/update.log 2>&1

echo "🔄 Начало автообновления в $(date)"
echo "📍 Текущая директория: $(pwd)"
echo "👤 Пользователь: $(whoami)"

REPO_DIR="{Path.cwd()}"
SERVICE_NAME="gpttg-bot"

cd "$REPO_DIR" || {{
    echo "❌ Не удалось перейти в директорию $REPO_DIR"
    exit 1
}}

echo "🔍 Содержимое директории:"
ls -la

# Сохраняем важные файлы
echo "💾 Сохранение важных файлов..."
cp .env .env.backup 2>/dev/null && echo "✅ .env сохранён" || echo "⚠️ .env не найден"
cp bot/bot.sqlite bot.sqlite.backup 2>/dev/null && echo "✅ база сохранена" || echo "⚠️ база не найдена"

# Останавливаем сервис
echo "🛑 Остановка сервиса..."
if systemctl stop $SERVICE_NAME; then
    echo "✅ Сервис остановлен"
else
    echo "⚠️ Ошибка остановки сервиса, но продолжаем"
fi

# Обновляем код
echo "📥 Обновление кода..."
if git fetch origin; then
    echo "✅ git fetch выполнен"
else
    echo "❌ Ошибка git fetch"
    exit 1
fi

if git reset --hard origin/master; then
    echo "✅ git reset выполнен"
else
    echo "❌ Ошибка git reset"
    exit 1
fi

# Восстанавливаем файлы
echo "🔄 Восстановление файлов..."
mv .env.backup .env 2>/dev/null && echo "✅ .env восстановлен" || echo "⚠️ .env не восстановлен"
mv bot.sqlite.backup bot/bot.sqlite 2>/dev/null && echo "✅ база восстановлена" || echo "⚠️ база не восстановлена"

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

# Обновляем systemd сервис если нужно
if [ -f "gpttg-bot.service" ]; then
    echo "⚙️ Обновление systemd сервиса..."
    cp gpttg-bot.service /etc/systemd/system/
    systemctl daemon-reload
    echo "✅ Systemd сервис обновлён"
fi

# Запускаем сервис
echo "🚀 Запуск сервиса..."
if systemctl start $SERVICE_NAME; then
    echo "✅ Команда запуска выполнена"
else
    echo "❌ Ошибка команды запуска"
    exit 1
fi

# Проверяем статус с расширенным ожиданием
echo "⏳ Ожидание запуска сервиса..."
for i in {{1..10}}; do
    sleep 2
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✅ Сервис запущен успешно! Попытка $i/10"
        systemctl status $SERVICE_NAME --no-pager --lines=3
        echo "🎉 Обновление завершено успешно в $(date)"
        exit 0
    else
        echo "⏳ Попытка $i/10: сервис ещё не запущен..."
    fi
done

echo "❌ Сервис не запустился за 20 секунд"
echo "📋 Статус сервиса:"
systemctl status $SERVICE_NAME --no-pager
echo "📋 Последние логи:"
journalctl -u $SERVICE_NAME --no-pager --lines=10
exit 1
"""
        
        try:
            with open(SimpleUpdater.UPDATE_SCRIPT_PATH, "w") as f:
                f.write(script_content)
            os.chmod(SimpleUpdater.UPDATE_SCRIPT_PATH, 0o755)
            logger.info(f"Скрипт обновления создан: {SimpleUpdater.UPDATE_SCRIPT_PATH}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания скрипта обновления: {e}")
            return False
    
    @staticmethod
    async def start_update() -> tuple[bool, str]:
        """Запускает процесс обновления."""
        if not settings.is_linux:
            return False, "Автообновление доступно только на Linux"
        
        if not SimpleUpdater.create_update_script():
            return False, "Не удалось создать скрипт обновления"
        
        logger.info("Запуск процесса автообновления...")
        
        try:
            # Сначала проверяем, доступна ли команда at
            at_check = subprocess.run(
                "command -v at && systemctl is-active --quiet atd", 
                shell=True, 
                capture_output=True, 
                timeout=3
            )
            
            if at_check.returncode == 0:
                # Используем at для отложенного выполнения
                logger.info("Используем команду 'at' для отложенного обновления")
                cmd = f"echo '{SimpleUpdater.UPDATE_SCRIPT_PATH}' | at now + 3 seconds"
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if result.returncode == 0:
                    logger.info("Обновление запланировано через 'at'")
                    return True, "Обновление запущено через 'at' и будет выполнено через 3 секунды"
                else:
                    logger.warning(f"Ошибка 'at': {result.stderr}")
                    raise Exception("at failed")
            else:
                logger.warning("Команда 'at' недоступна, используем nohup")
                raise Exception("at not available")
                
        except Exception:
            # Fallback к nohup
            try:
                logger.info("Используем nohup для фонового обновления")
                cmd = f"nohup {SimpleUpdater.UPDATE_SCRIPT_PATH} &"
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=3
                )
                
                if result.returncode == 0:
                    logger.info("Обновление запущено через nohup")
                    return True, "Обновление запущено в фоновом режиме"
                else:
                    logger.error(f"Ошибка nohup: {result.stderr}")
                    return False, f"Ошибка запуска через nohup: {result.stderr[:100]}"
                    
            except subprocess.TimeoutExpired:
                return False, "Превышено время ожидания запуска обновления"
            except Exception as e:
                logger.error(f"Ошибка запуска обновления: {e}")
                return False, f"Критическая ошибка: {str(e)[:100]}"