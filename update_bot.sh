#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ────────────────────────────────────────────────────
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"

# 🔄 Очищаем предыдущий лог
: > "$LOG_FILE"

# ── Конфигурация выхода ─────────────────────────────────────────────────────
# 1) Всегда пишем в файл
# 2) Если есть systemd-cat ⇒ пишем в журнал
# 3) Если есть интерактивный TTY (ручной запуск) ⇒ дублируем в консоль
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

log "▶️  Начало обновления"

cd "$REPO_DIR"

# Poetry‑виртуалка всегда в каталоге проекта
export POETRY_VIRTUALENVS_IN_PROJECT=true
# 👉 PATH включает каталог Poetry
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

log "📦  Получаем изменения из Git"
git fetch --all
LATEST_HASH=$(git rev-parse --short origin/beta)
log "ℹ️  Целевая версия $LATEST_HASH"
git reset --hard origin/beta

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
UNIT_SRC="$REPO_DIR/gpttg-bot.service"
UNIT_DST="/etc/systemd/system/gpttg-bot.service"
log "📝  Копирую unit‑файл -> $UNIT_DST"
cp -f "$UNIT_SRC" "$UNIT_DST"

log "🚀  Перезапуск systemd‑сервиса"
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

log "✅  Обновление завершено. Версия $REVISION"
```bash
#!/usr/bin/env bash
# ── Авто‑обновление GPTTG ────────────────────────────────────────────────────
set -euo pipefail

SERVICE_NAME="gpttg-bot"
REPO_DIR="/root/GPTTG"
LOG_FILE="/var/log/gpttg-update.log"

# 🔄 Очищаем предыдущий лог
: > "$LOG_FILE"

# Выбираем канал логирования: systemd‑journal, если systemd-cat доступен
if command -v systemd-cat &>/dev/null; then
  exec > >(tee -a "$LOG_FILE" | systemd-cat -t gpttg-update) 2>&1
else
  echo "[warn] systemd-cat not found; logging только в $LOG_FILE"
  exec >> "$LOG_FILE" 2>&1
fi

log() { printf '[%s] %s
' "$(date -Iseconds)" "$*"; }
trap 'log "❌  Ошибка на строке $LINENO"' ERR

log "▶️  Начало обновления"

cd "$REPO_DIR"

# Poetry‑виртуалка всегда в каталоге проекта
export POETRY_VIRTUALENVS_IN_PROJECT=true
# 👉 PATH включает каталог Poetry
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:$PATH"

log "📦  Получаем изменения из Git"
git fetch --all
LATEST_HASH=$(git rev-parse --short origin/beta)
log "ℹ️  Целевая версия $LATEST_HASH"
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
UNIT_SRC="$REPO_DIR/gpttg-bot.service"
UNIT_DST="/etc/systemd/system/gpttg-bot.service"
log "📝  Копирую unit‑файл -> $UNIT_DST"
cp -f "$UNIT_SRC" "$UNIT_DST"

log "🚀  Перезапуск systemd‑сервиса"
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

log "✅  Обновление завершено. Версия $REVISION"