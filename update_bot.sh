#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ────────────────────────────────────────────────────
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"
# Укажите ветку для прода (по умолчанию beta). Можно переопределить
TARGET_BRANCH="${1:-${TARGET_BRANCH:-master}}"

# 🔄 Очищаем предыдущий лог, чтобы каждая сессия начиналась с нуля
: > "$LOG_FILE"

# ── Конфигурация вывода ─────────────────────────────────────────────────────
if command -v systemd-cat &>/dev/null; then
  if [ -t 1 ]; then
    exec > >(tee -a "$LOG_FILE" | tee /dev/tty | systemd-cat -t gpttg-update) 2>&1
  else
    exec > >(tee -a "$LOG_FILE" | systemd-cat -t gpttg-update) 2>&1
  fi
else
  if [ -t 1 ]; then
    exec > >(tee -a "$LOG_FILE" | tee /dev/tty) 2>&1
  else
    exec >> "$LOG_FILE" 2>&1
  fi
fi

log() { printf '[%s] %s
' "$(date -Iseconds)" "$*"; }
trap 'log "❌  Ошибка на строке $LINENO"' ERR

log "▶️  Начало обновления (ветка $TARGET_BRANCH)"

cd "$REPO_DIR"

# Poetry‑виртуалка внутри проекта
export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

# ── Git pull ────────────────────────────────────────────────────────────────
log "📦  git fetch origin $TARGET_BRANCH"
if ! git fetch origin "$TARGET_BRANCH"; then
  log "⚠️  Не удалось fetch origin/$TARGET_BRANCH — пробую master"
  TARGET_BRANCH="master"
  git fetch origin "$TARGET_BRANCH"
fi

if ! git show-ref --verify --quiet "refs/remotes/origin/$TARGET_BRANCH"; then
  log "❗  origin/$TARGET_BRANCH не существует. Завершаю."
  exit 1
fi

LATEST_HASH=$(git rev-parse --short "origin/$TARGET_BRANCH")
log "ℹ️  Целевая версия $LATEST_HASH"

git reset --hard "origin/$TARGET_BRANCH"
REVISION="$LATEST_HASH"

# ── Poetry & зависимости ────────────────────────────────────────────────────
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  python3 -m pip install --upgrade --user poetry
fi

if [[ ! -x .venv/bin/python ]]; then
  log "📚  .venv отсутствует — создаю"
  poetry install --only=main --no-interaction --no-ansi
fi

log "🔄  poetry install"
poetry install --only=main --no-interaction --no-ansi

# ── Переписываем unit‑файл ───────────────────────────────────────────────────
UNIT_SRC="$REPO_DIR/gpttg-bot.service"
UNIT_DST="/etc/systemd/system/gpttg-bot.service"
log "📝  Копирую unit‑файл -> $UNIT_DST"
cp -f "$UNIT_SRC" "$UNIT_DST"

# ── Перезапуск ───────────────────────────────────────────────────────────────
log "🚀  daemon-reload + restart"
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

log "✅  Обновление завершено. Версия $REVISION"