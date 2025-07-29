#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ─────────────────────────────────────────────
# Скрипт можно запускать вручную или из‑под работающего бота.
#   --no-restart     — отложить рестарт бота через systemd‑run (нужно, когда
#                      скрипт вызывается самим ботом и нельзя убивать текущий
#                      процесс).
#   --branch=<ветка> — обновиться до указанной ветки (по умолчанию master).

set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"
TARGET_BRANCH="master"
RESTART=true

# ── Обработка аргументов ──────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=false ;;
    --branch=*)   TARGET_BRANCH="${arg#*=}" ;;
  esac
done

# ── Подготавливаем лог ────────────────────────────────────────────────
> "$LOG_FILE"   # очистка файла

# ── Настройка вывода: файл + journald + консоль (если интерактивно) ───
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

log() { printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }
trap 'log "❌  Ошибка на строке $LINENO"' ERR

log "▶️  Запускаю обновление (ветка $TARGET_BRANCH, перезапуск=$RESTART)"
cd "$REPO_DIR"

log "⚠️  остановка бота"
    systemctl stop "$SERVICE_NAME"

export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

# ── Обновляем код ─────────────────────────────────────────────────────
log "📦  git fetch origin $TARGET_BRANCH"
git fetch origin "$TARGET_BRANCH"
NEW_HASH=$(git rev-parse --short "origin/$TARGET_BRANCH")
log "ℹ️  Обновляемся до $NEW_HASH"
git reset --hard "origin/$TARGET_BRANCH"

# ── Poetry ────────────────────────────────────────────────────────────
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  python3 -m pip install --user --upgrade poetry
fi

log "🔐  Обновляю lock‑файл"
poetry lock --no-interaction --no-ansi

log "🔄  Устанавливаю зависимости"
poetry install --only=main --no-interaction --no-ansi

# ── Обновляем unit‑файл бота ──────────────────────────────────────────
UNIT_SRC="$REPO_DIR/gpttg-bot.service"
UNIT_DST="/etc/systemd/system/gpttg-bot.service"
log "📝  Копирую unit‑файл в $UNIT_DST"
cp -f "$UNIT_SRC" "$UNIT_DST"
log "📝  gpttg-bot.service"
TIMER_SRC="$REPO_DIR/bot/deploy/systemd/gpttg-update.timer"
SERVICE_SRC="$REPO_DIR/bot/deploy/systemd/gpttg-update.service"

cp -f "$SERVICE_SRC" /etc/systemd/system/gpttg-update.service
log "📝  gpttg-update.service"
cp -f "$TIMER_SRC"   /etc/systemd/system/gpttg-update.timer
log "📝  gpttg-update.timer"

systemctl daemon-reload

# ── Перезапуск бота ───────────────────────────────────────────────────
if $RESTART; then
  log "🚀  Перезапускаю $SERVICE_NAME немедленно"
  systemctl restart "$SERVICE_NAME"
else
  if command -v systemd-run &>/dev/null; then
    log "🕒  Планирую отложенный рестарт через systemd-run (5 с)"
    systemd-run --unit=gpttg-restart --on-active=5s \
      /usr/bin/systemctl restart "$SERVICE_NAME"
  else
    log "⚠️  systemd-run не найден — перезапускаю без блокировки"
    systemctl restart "$SERVICE_NAME" --no-block
  fi
fi

# ── Читаем версию из pyproject.toml ───────────────────────────────────
VERSION=$(grep -m1 '^version' pyproject.toml | cut -d '"' -f2)
log "✅  Обновление завершено. Версия $VERSION ($NEW_HASH)"
