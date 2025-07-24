#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ─────────────────────────────────────────────
# Поддерживает флаг --no-restart, чтобы скрипт можно было вызывать
# из‑под работающего бота (например, по команде /update в Telegram).
# В этом случае перезапуск сервиса откладывается через systemd‑run.
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"
TARGET_BRANCH="master"
RESTART=true

# ── Аргументы ──
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=false ;;
    --branch=*)   TARGET_BRANCH="${arg#*=}" ;;
  esac
done

: > "$LOG_FILE"   # очищаем лог

# ── Настройка вывода ──
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

log "▶️  Начало обновления (ветка $TARGET_BRANCH, restart=$RESTART)"
cd "$REPO_DIR"

export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

# ── Git fetch/reset ──
log "📦  git fetch origin $TARGET_BRANCH"
git fetch origin "$TARGET_BRANCH"
LATEST_HASH=$(git rev-parse --short "origin/$TARGET_BRANCH")
log "ℹ️  Целевая версия $LATEST_HASH"
git reset --hard "origin/$TARGET_BRANCH"
REVISION="$LATEST_HASH"

# ── Poetry ──
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  python3 -m pip install --upgrade --user poetry
fi

log "🔐  Генерирую lock‑файл"
poetry lock --no-interaction --no-ansi

log "🔄  poetry install"
poetry install --only=main --no-interaction --no-ansi

# ── Обновляем unit‑файл ──
UNIT_SRC="$REPO_DIR/gpttg-bot.service"
UNIT_DST="/etc/systemd/system/gpttg-bot.service"
log "📝  Копирую unit‑файл → $UNIT_DST"
cp -f "$UNIT_SRC" "$UNIT_DST"

# ── Перезапуск ──
if $RESTART; then
  log "🚀  daemon-reload + restart (тот же cgroup)"
  systemctl daemon-reload
  systemctl restart "$SERVICE_NAME"
else
  log "🕒  Планирую отложенный restart через systemd-run"
  systemctl daemon-reload
  systemd-run --on-active=5s --unit=gpttg-restart.service \
    /usr/bin/systemctl restart "$SERVICE_NAME"
fi

log "✅  Обновление завершено. Версия $REVISION"
```bash
#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ────────────────────────────────────────────────────
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"
TARGET_BRANCH="${1:-${TARGET_BRANCH:-master}}"  # default master

: > "$LOG_FILE"  # очистка лога

# ── Настройка вывода ──
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

export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

# ── Git fetch/reset ──
log "📦  git fetch origin $TARGET_BRANCH"
git fetch origin "$TARGET_BRANCH"
LATEST_HASH=$(git rev-parse --short "origin/$TARGET_BRANCH")
log "ℹ️  Целевая версия $LATEST_HASH"
git reset --hard "origin/$TARGET_BRANCH"
REVISION="$LATEST_HASH"

# ── Poetry env ──
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  python3 -m pip install --upgrade --user poetry
fi

# ── Генерируем/обновляем lock и ставим зависимости ──
log "🔐  Генерирую lock‑файл"
poetry lock --no-interaction --no-ansi

log "🔄  poetry install"
poetry install --only=main --no-interaction --no-ansi

# ── Unit file ──
UNIT_SRC="$REPO_DIR/gpttg-bot.service"
UNIT_DST="/etc/systemd/system/gpttg-bot.service"
log "📝  Копирую unit‑файл -> $UNIT_DST"
cp -f "$UNIT_SRC" "$UNIT_DST"

log "🚀  daemon-reload + restart"
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

log "✅  Обновление завершено. Версия $REVISION"