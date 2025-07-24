#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ────────────────────────────────────────────────────
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"

# 🔄 Очищаем предыдущий лог
: > "${LOG_FILE}"

# Записываем вывод и в файл, и в systemd‑journal (тег gpttg-update)
exec > >(tee -a "${LOG_FILE}" | systemd-cat -t gpttg-update) 2>&1

log() { printf '[%s] %s
' "$(date -Iseconds)" "$*"; }

log "▶️  Начало обновления"

cd "${REPO_DIR}"

# Poetry‑виртуалка всегда в каталоге проекта
export POETRY_VIRTUALENVS_IN_PROJECT=true
# 👉 PATH включает каталог Poetry
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

log "📦  Получаем изменения из Git"
git fetch --all
git reset --hard origin/beta

# Сохраняем версию после reset
REVISION="$(git rev-parse --short HEAD)"

# Ставим Poetry, если вдруг нет
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  python3 -m pip install --upgrade --user poetry
fi

# Создаём .venv, если потерялась
if [[ ! -x .venv/bin/python ]]; then
  log "📚  .venv отсутствует — создаю заново"
  poetry install --only=main --no-interaction --no-ansi
fi

log "🔄  Обновляю зависимости"
poetry install --only=main --no-interaction --no-ansi

# Копируем свежий unit‑файл
log "📝  Копирую unit‑файл"
cp -f "${REPO_DIR}/gpttg-bot.service" /etc/systemd/system/gpttg-bot.service

log "🚀  Перезапуск systemd‑сервиса"
systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"

log "✅  Обновление завершено. Версия ${REVISION}"