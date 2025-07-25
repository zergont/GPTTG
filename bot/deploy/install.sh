#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(dirname "$(readlink -f "$0")")/.."   # корень GPTTG
cd "$REPO_DIR"

echo "📦  Копируем unit‑файлы…"
sudo cp gpttg-bot.service                     /etc/systemd/system/
sudo cp bot/deploy/systemd/gpttg-update.*     /etc/systemd/system/

echo "🔧  Делаем update_bot.sh исполняемым…"
sudo chmod +x "$REPO_DIR/update_bot.sh"

echo "🔄  Обновляем systemd…"
sudo systemctl daemon-reload

# 🟢  Теперь перезапускаем/включаем всё необходимое
echo "🚀  Запускаем службы…"
sudo systemctl enable --now gpttg-bot.service
sudo systemctl enable --now gpttg-update.timer

echo "✅ GPTTG установлен и запущен."
