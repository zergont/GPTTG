#!/usr/bin/env bash
# ── Установка GPTTG на сервер ─────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"   # bot/deploy
REPO_DIR="$(dirname "$SCRIPT_DIR")/.."          # корень GPTTG

cd "$REPO_DIR"

echo "📦  Копируем systemd‑unit‑файлы…"
sudo cp gpttg-bot.service                    /etc/systemd/system/
sudo cp bot/deploy/systemd/gpttg-update.*    /etc/systemd/system/

echo "🔧  Делаем update_bot.sh исполняемым…"
sudo chmod +x "$REPO_DIR/update_bot.sh"

echo "🔄  Перезагружаем systemd и запускаем службы…"
sudo systemctl daemon-reload
sudo systemctl enable --now gpttg-bot.service
sudo systemctl enable --now gpttg-update.timer

echo "✅ GPTTG установлен и запущен."
