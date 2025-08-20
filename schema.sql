-- Последний response‑id для чата, чтобы использовать `previous_response_id`
CREATE TABLE IF NOT EXISTS chat_history (
    chat_id       INTEGER PRIMARY KEY,
    last_response TEXT
);

-- Информация о пользователях
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    last_name     TEXT,
    first_seen    DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_welcomed   BOOLEAN DEFAULT FALSE
);

-- Настройки бота (для админа)
CREATE TABLE IF NOT EXISTS bot_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Учёт всех вызовов моделей (включая Whisper и DALL·E)
CREATE TABLE IF NOT EXISTS usage (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER,
    user_id   INTEGER,
    tokens    INTEGER DEFAULT 0,
    cost      REAL    NOT NULL,
    model     TEXT    NOT NULL,
    ts        DATETIME DEFAULT CURRENT_TIMESTAMP
);
-- Таблица для хранения file_id загруженных в OpenAI файлов
CREATE TABLE IF NOT EXISTS openai_files (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    file_id    TEXT NOT NULL,
    uploaded   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usage_chat_id ON usage(chat_id);
CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_model ON usage(model);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage(ts);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_openai_files_chat_id ON openai_files(chat_id);

-- Напоминания (одноразовые, с поддержкой цепочек)
CREATE TABLE IF NOT EXISTS reminders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id          INTEGER NOT NULL,
    user_id          INTEGER NOT NULL,
    text             TEXT    NOT NULL,
    due_at           DATETIME NOT NULL,   -- UTC
    silent           INTEGER DEFAULT 0,   -- 0/1
    status           TEXT    DEFAULT 'scheduled',
    executed_at      DATETIME,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- служебные поля для воркера и цепочек
    picked_at        DATETIME,            -- когда задача взята воркером
    fired_at         DATETIME,            -- когда сообщение фактически отправлено
    idempotency_key  TEXT,                -- ключ для защиты от повторной отправки
    meta_json        TEXT                 -- JSON: {next_offset, next_at, steps_left, end_at, silent, ...}
);
CREATE INDEX IF NOT EXISTS idx_reminders_due_status ON reminders(status, due_at);
CREATE INDEX IF NOT EXISTS idx_reminders_chat ON reminders(chat_id);
-- частичный уникальный индекс по идемпотентности (если ключ установлен)
CREATE UNIQUE INDEX IF NOT EXISTS idx_reminders_idemp ON reminders(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Вставляем дефолтную модель
INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('current_model', 'gpt-4o-mini');