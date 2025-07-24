#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(dirname "$(readlink -f "$0")")/.."   # корень репо
cd "$REPO_DIR"

# 1️⃣  Копируем unit‑файлы
sudo cp gpttg-bot.service            /etc/systemd/system/
sudo cp deploy/systemd/gpttg-update.* /etc/systemd/system/

# 2️⃣  Делаем скрипт обновления исполняемым
sudo chmod +x "$REPO_DIR/update_bot.sh"

# 3️⃣  Регистрируем службу и таймер
sudo systemctl daemon-reload
sudo systemctl enable --now gpttg-bot.service
sudo systemctl enable --now gpttg-update.timer

echo "✅ GPTTG установлен и запущен."