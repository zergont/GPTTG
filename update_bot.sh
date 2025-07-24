#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ────────────────────────────────────────────────────
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"

# Записываем вывод и в файл, и в systemd‑journal (тег gpttg-update)
exec > >(tee -a "${LOG_FILE}" | systemd-cat -t gpttg-update) 2>&1

log() { printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }

log "▶️  Начало обновления"

cd "${REPO_DIR}"

# Poetry‑виртуалка всегда в каталоге проекта
export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:$PATH"

log "📦  Получаем изменения из Git"
git fetch --all
git reset --hard origin/beta

# Ставим Poetry, если вдруг нет (через python3 - m pip)
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  python3 -m pip install --upgrade poetry
fi

# Создаём .venv, если потерялся
if [[ ! -x .venv/bin/python ]]; then
  log "📚  .venv отсутствует — создаю заново"
  poetry install --only=main --no-interaction --no-ansi
fi

log "🔄  Обновляю зависимости"
poetry install --only=main --no-interaction --no-ansi

log "🚀  Перезапуск systemd‑сервиса"
systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"

log "✅  Обновление завершено успешно"
