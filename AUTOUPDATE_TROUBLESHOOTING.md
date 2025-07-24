# Диагностика проблем автообновления GPTTG

## Проблема: Бот не перезапускается после автообновления

### 🔍 Шаги диагностики:

#### 1. Проверьте статус сервиса
```bash
sudo systemctl status gpttg-bot
```

#### 2. Проверьте логи обновления
Используйте команду в боте:
```
/updatelogs
```
Или проверьте файлы вручную:
```bash
cat /tmp/update.log
cat /tmp/simple_update.log
```

#### 3. Протестируйте систему обновления
Используйте команду в боте:
```
/updatetest
```

#### 4. Проверьте логи сервиса
```bash
sudo journalctl -u gpttg-bot --lines=20
```

#### 5. Ручной перезапуск для проверки
```bash
sudo systemctl start gpttg-bot
sudo systemctl status gpttg-bot
```

### 🛠️ Частые проблемы и решения:

#### Проблема 1: Команда 'at' недоступна
**Симптомы:** В логах ошибка "at command not found"
**Решение:**
```bash
sudo apt update
sudo apt install -y at
sudo systemctl enable --now atd
```

#### Проблема 2: Ошибки git
**Симптомы:** В логах ошибки git fetch/reset
**Решение:**
```bash
cd /root/GPTTG
git status
git fetch origin
git reset --hard origin/master
```

#### Проблема 3: Проблемы с зависимостями
**Симптомы:** Ошибки poetry install или pip install
**Решение:**
```bash
cd /root/GPTTG
export PATH="$HOME/.local/bin:$PATH"
poetry install --only=main
# или
pip install -r requirements.txt
```

#### Проблема 4: Права доступа
**Симптомы:** Permission denied в логах
**Решение:**
```bash
sudo chown -R root:root /root/GPTTG
sudo chmod +x /root/GPTTG/update_bot.sh
```

#### Проблема 5: Повреждённые файлы конфигурации
**Симптомы:** Сервис не запускается после обновления
**Решение:**
```bash
cd /root/GPTTG
# Проверяем .env
ls -la .env*
# Восстанавливаем из бэкапа если нужно
cp .env.backup .env 2>/dev/null || echo "Бэкап не найден"
```

### 🚀 Экстренное восстановление:

Если автообновление полностью сломалось:

```bash
# 1. Остановить сервис
sudo systemctl stop gpttg-bot

# 2. Ручное обновление
cd /root/GPTTG
sudo ./update_bot.sh

# 3. Если update_bot.sh не работает - упрощённое обновление:
git fetch origin
git reset --hard origin/master
poetry install --only=main
sudo systemctl start gpttg-bot
```

### 📊 Проверка после исправления:

1. **Статус сервиса:**
   ```bash
   sudo systemctl status gpttg-bot
   ```

2. **Активность бота:**
   - Отправьте `/start` боту в Telegram
   - Проверьте ответ

3. **Автообновление:**
   ```
   /updatetest
   ```

4. **Логи в реальном времени:**
   ```bash
   sudo journalctl -u gpttg-bot -f
   ```

### 🎯 Профилактика:

1. **Регулярная проверка статуса:**
   ```bash
   # Добавьте в cron для ежедневной проверки
   0 12 * * * systemctl is-active --quiet gpttg-bot || systemctl restart gpttg-bot
   ```

2. **Мониторинг логов:**
   - Регулярно проверяйте `/updatelogs` в боте
   - Следите за размером лог-файлов в /tmp

3. **Бэкапы:**
   - Убедитесь, что .env и база данных регулярно копируются
   - Проверяйте наличие .env.backup после обновлений

### 📞 Если ничего не помогает:

1. Сохраните логи:
   ```bash
   sudo journalctl -u gpttg-bot > /tmp/service-logs.txt
   cat /tmp/update.log > /tmp/update-logs.txt
   ```

2. Проверьте основные файлы:
   ```bash
   ls -la /root/GPTTG/.env
   ls -la /root/GPTTG/bot/main.py
   ls -la /root/GPTTG/.venv/bin/python3
   ```

3. Полная переустановка (крайний случай):
   ```bash
   # Сохраните .env и базу
   cp /root/GPTTG/.env /root/env-backup
   cp /root/GPTTG/bot/bot.sqlite /root/db-backup
   
   # Переклонируйте репозиторий
   rm -rf /root/GPTTG
   git clone https://github.com/zergont/GPTTG.git /root/GPTTG
   cd /root/GPTTG
   
   # Восстановите файлы
   cp /root/env-backup .env
   cp /root/db-backup bot/bot.sqlite
   
   # Настройте заново
   poetry install
   sudo ./update_bot.sh
   ```