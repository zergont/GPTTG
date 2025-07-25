#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"   # bot/deploy
REPO_DIR="$(dirname "$SCRIPT_DIR")/.."          # корень GPTTG
cd "$REPO_DIR"

echo "📦  Копирую systemd-unit-файлы…"
sudo cp gpttg-bot.service                       /etc/systemd/system/
sudo cp bot/deploy/systemd/gpttg-update.service /etc/systemd/system/
sudo cp bot/deploy/systemd/gpttg-update.timer   /etc/systemd/system/

echo "🔧  Делаю update_bot.sh исполняемым…"
sudo chmod +x "$REPO_DIR/update_bot.sh"

echo "🔄  Перезагружаю systemd и запускаю службы…"
sudo systemctl daemon-reload
sudo systemctl enable --now gpttg-bot.service
sudo systemctl enable --now gpttg-update.timer

BOT_STATUS=$(systemctl is-active gpttg-bot.service)
TIMER_STATUS=$(systemctl is-active gpttg-update.timer)
echo "✅ GPTTG установлен. Бот: $BOT_STATUS, Таймер: $TIMER_STATUS"

echo "✅  Перезагружаю бота"
sudo systemctl restart gpttg-bot.service