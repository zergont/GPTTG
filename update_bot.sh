#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ─────────────────────────────────────────────
# Скрипт можно запускать вручную или из‑под работающего бота.
#   --no-restart     — отложить рестарт бота через systemd‑run (нужно, когда
#                      скрипт вызывается самим ботом и нельзя убивать текущий
#                      процесс).
#   --branch=<ветка> — обновиться до указанной ветки (по умолчанию master).
#   --force          — принудительное обновление без проверки изменений.

set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"
TARGET_BRANCH="master"
RESTART=true
FORCE_UPDATE=false

# ── Обработка аргументов ──────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=false ;;
    --branch=*)   TARGET_BRANCH="${arg#*=}" ;;
    --force)      FORCE_UPDATE=true ;;
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

log "▶️  Запускаю проверку обновлений (ветка $TARGET_BRANCH)"
cd "$REPO_DIR"


export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

# ── Проверяем наличие обновлений ──────────────────────────────────────
log "🔍  Проверяю наличие обновлений..."
git fetch origin "$TARGET_BRANCH"

CURRENT_HASH=$(git rev-parse --short HEAD)
REMOTE_HASH=$(git rev-parse --short "origin/$TARGET_BRANCH")

log "📍  Текущий commit: $CURRENT_HASH"
log "📍  Удаленный commit: $REMOTE_HASH"

# Проверяем количество коммитов отставания
COMMITS_BEHIND=$(git rev-list --count HEAD..origin/$TARGET_BRANCH)

if [ "$COMMITS_BEHIND" -eq 0 ] && [ "$FORCE_UPDATE" = false ]; then
  log "✅  Обновления не требуются. Текущая версия актуальна."
  exit 0
fi

if [ "$COMMITS_BEHIND" -gt 0 ]; then
  log "🔄  Найдено $COMMITS_BEHIND новых коммитов. Начинаю обновление..."
elif [ "$FORCE_UPDATE" = true ]; then
  log "⚡  Принудительное обновление (--force)..."
fi

# ── Обновляем код ─────────────────────────────────────────────────────
log "📦  Обновляю код до $REMOTE_HASH"
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
    log "🕒  Планирую отложенный рестарт через systemd-run (5 с)"
    systemd-run --unit=gpttg-restart --on-active=5s \
      /usr/bin/systemctl restart "$SERVICE_NAME"
  else
    log "⚠️  systemd-run не найден — перезапускаю без блокировки"
    systemctl restart "$SERVICE_NAME" --no-block
  fi
fi

# ── Читаем версию из pyproject.toml ───────────────────────────────────
VERSION=$(grep -m1 '^version' pyproject.toml | cut -d '"' -f2)
log "✅  Обновление завершено. Версия $VERSION ($REMOTE_HASH)"
