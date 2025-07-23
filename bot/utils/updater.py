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
            url = "https://raw.githubusercontent.com/zergont/GPTTG/beta/pyproject.toml"
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
set -e

REPO_DIR="{Path.cwd()}"
SERVICE_NAME="gpttg-bot"

echo "🔄 Начало автообновления в $(date)"
cd "$REPO_DIR"

# Сохраняем важные файлы
cp .env .env.backup 2>/dev/null || true
cp bot/bot.sqlite bot.sqlite.backup 2>/dev/null || true

# Останавливаем сервис
echo "🛑 Остановка сервиса..."
systemctl stop $SERVICE_NAME

# Обновляем код
echo "📥 Обновление кода..."
git fetch origin
git reset --hard origin/beta

# Восстанавливаем файлы
mv .env.backup .env 2>/dev/null || true
mv bot.sqlite.backup bot/bot.sqlite 2>/dev/null || true

# Обновляем зависимости
echo "📦 Обновление зависимостей..."
export PATH="$HOME/.local/bin:$PATH"
poetry install --only=main 2>/dev/null || pip install -r requirements.txt

# Перезапускаем сервис
echo "🚀 Запуск сервиса..."
systemctl start $SERVICE_NAME

# Проверяем статус
sleep 5
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "✅ Обновление завершено успешно!"
    systemctl status $SERVICE_NAME --no-pager --lines=3
else
    echo "❌ Ошибка запуска сервиса"
    journalctl -u $SERVICE_NAME --no-pager --lines=5
    exit 1
fi
"""
        
        try:
            with open(SimpleUpdater.UPDATE_SCRIPT_PATH, "w") as f:
                f.write(script_content)
            os.chmod(SimpleUpdater.UPDATE_SCRIPT_PATH, 0o755)
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
        
        try:
            # Запускаем скрипт с отложенным выполнением
            cmd = f"echo '{SimpleUpdater.UPDATE_SCRIPT_PATH}' | at now + 5 seconds"
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "Обновление запущено и будет выполнено через 5 секунд"
            else:
                # Fallback к nohup если at недоступен
                cmd = f"nohup {SimpleUpdater.UPDATE_SCRIPT_PATH} > /tmp/update.log 2>&1 &"
                result = subprocess.run(cmd, shell=True, timeout=3)
                return True, "Обновление запущено в фоновом режиме"
                
        except subprocess.TimeoutExpired:
            return False, "Превышено время ожидания запуска обновления"
        except Exception as e:
            logger.error(f"Ошибка запуска обновления: {e}")
            return False, f"Ошибка: {str(e)[:100]}"