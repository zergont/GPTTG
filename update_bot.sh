```bash
#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ─────────────────────────────────────────────
# Скрипт можно запускать вручную или из‑под работающего бота.
#   * по умолчанию он перезапускает службу бота в конце;
#   * флаг --no-restart откладывает перезапуск (удобно для /update в Telegram).
# В этом случае systemd‑run создаёт transient‑unit, который рестартует бота
# спустя 5 секунд — уже после завершения скрипта и отправки ответа в чат.
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"
TARGET_BRANCH="master"   # можно сменить параметром --branch=<ветка>
RESTART=true

# ── Обработка аргументов ──────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=false ;;
    --branch=*)   TARGET_BRANCH="${arg#*=}" ;;
  esac
done

: > "$LOG_FILE"   # очищаем лог перед новой сессией

# ── Настройка логирования ─────────────────────────────────────────────
# Пишем в файл, journald (если есть) и в консоль при ручном запуске.
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

log "▶️  Начинаю обновление (ветка $TARGET_BRANCH, перезапуск=$RESTART)"
cd "$REPO_DIR"

export POETRY_VIRTUALENVS_IN_PROJECT=true
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

# ── Получаем свежий код ───────────────────────────────────────────────
log "📦  Получаю изменения из origin/$TARGET_BRANCH"
git fetch origin "$TARGET_BRANCH"
LATEST_HASH=$(git rev-parse --short "origin/$TARGET_BRANCH")
log "ℹ️  Целевая версия $LATEST_HASH"
git reset --hard "origin/$TARGET_BRANCH"
REVISION="$LATEST_HASH"

# ── Poetry и зависимости ──────────────────────────────────────────────
if ! command -v poetry &>/dev/null; then
  log "🛠  Устанавливаю Poetry"
  python3 -m pip install --upgrade --user poetry
fi

log "🔐  Генерирую lock‑файл"
poetry lock --no-interaction --no-ansi

log "🔄  Устанавливаю зависимости poetry"
poetry install --only=main --no-interaction --no-ansi

# ── Обновляем unit‑файл бота ──────────────────────────────────────────
UNIT_SRC="$REPO_DIR/gpttg-bot.service"
UNIT_DST="/etc/systemd/system/gpttg-bot.service"
log "📝  Копирую unit‑файл → $UNIT_DST"
cp -f "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload

# ── Перезапуск службы ────────────────────────────────────────────────
if $RESTART; then
  log "🚀  Перезапускаю службу бота сразу (та же cgroup)"
  systemctl restart "$SERVICE_NAME"
else
  if command -v systemd-run &>/dev/null; then
    log "🕒  Планирую отложенный перезапуск через systemd-run (через 5 с)"
    systemd-run --on-active=5s --unit=gpttg-restart.service \
      /usr/bin/systemctl restart "$SERVICE_NAME"
    log "ℹ️  Транзитная служба gpttg-restart создана"
  else
    log "⚠️  systemd-run не найден → перезапуск без блокировки"
    systemctl restart "$SERVICE_NAME" --no-block
  fi
fi

log "✅  Обновление завершено. Версия $REVISION"
```
