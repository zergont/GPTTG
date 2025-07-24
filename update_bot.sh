#!/usr/bin/env bash
# Авто‑обновление GPTTG
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"

# Логируем вывод и в файл, и в systemd‑journal
exec > >(tee -a "${LOG_FILE}" | systemd-cat -t gpttg-update) 2>&1

log() {
  printf '[%s] %s
' "$(date -Iseconds)" "$*"
}

log "▶️  Начало обновления"

cd "${REPO_DIR}"

# Poetry virtualenv в каталоге проекта
export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="$HOME/.local/bin:$PATH"

log "📦  Получаем изменения из Git"
git fetch --all
git reset --hard origin/beta

# Устанавливаем Poetry, если вдруг нет
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  pip install --upgrade poetry
fi

# Создаём виртуалку, если потерялась
if [[ ! -x .venv/bin/python ]]; then
  log "📚  .venv отсутствует — создаю заново"
  poetry install --only=main --no-interaction --no-ansi
fi

log "🔄  Обновляю зависимости"
poetry install --only=main --no-interaction --no-ansi

log "🚀  Перезапуск systemd‑сервиса"
systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"

log "✅  Обновление завершено успешно"