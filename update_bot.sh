#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"

# Пишем в файл и journald
exec > >(tee -a "${LOG_FILE}" | systemd-cat -t gpttg-update) 2>&1
log() { printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }

log "▶️  Начало обновления"

cd "${REPO_DIR}"

# ⇢ виртуалка внутри проекта
export POETRY_VIRTUALENVS_IN_PROJECT=true

# 👉 PATH c /root/.local/bin
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

log "📦  Git pull"
git fetch --all
git reset --hard origin/master

# Poetry, если нет
if ! command -v poetry &>/dev/null; then
  log "🛠  Ставлю Poetry"
  python3 -m pip install --upgrade --user poetry
fi

# .venv, если потерялась
if [[ ! -x .venv/bin/python ]]; then
  log "📚  Создаю .venv"
  poetry install --only=main --no-interaction --no-ansi
fi

log "🔄  Обновляю deps"
poetry install --only=main --no-interaction --no-ansi

# Копируем свежий unit‑файл
log "📝  Копирую unit‑файл"
cp -f "${REPO_DIR}/gpttg-bot.service" /etc/systemd/system/gpttg-bot.service

log "🚀  daemon‑reload + restart"
systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"

log "✅  Готово"
