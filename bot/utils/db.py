"""Оптимизированная обёртка над aiosqlite с пулом соединений."""
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
import logging
from aiogram.types import User
import asyncio
import pytz
_schema_applied = False
_schema_lock = asyncio.Lock()


DB_PATH = Path(__file__).with_suffix(".db").parent.parent / "bot.sqlite"
logger = logging.getLogger(__name__)

# Пул соединений (простая реализация)
_connection_pool = []
_pool_lock = asyncio.Lock()
MAX_POOL_SIZE = 5


@asynccontextmanager
async def get_conn():
    """Возвращает соединение из пула."""
    async with _pool_lock:
        if _connection_pool:
            db = _connection_pool.pop()
        else:
            db = await aiosqlite.connect(DB_PATH)
            # Настройки производительности
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=10000")
            await db.execute("PRAGMA temp_store=MEMORY")

    try:
        yield db
    finally:
        async with _pool_lock:
            if len(_connection_pool) < MAX_POOL_SIZE:
                _connection_pool.append(db)
            else:
                await db.close()


async def _ensure_users_timezone_column():
    """Гарантирует наличие столбца users.timezone."""
    async with get_conn() as db:
        try:
            cur = await db.execute("PRAGMA table_info(users)")
            cols = await cur.fetchall()
            col_names = {c[1] for c in cols}
            if "timezone" not in col_names:
                await db.execute("ALTER TABLE users ADD COLUMN timezone TEXT")
                await db.commit()
        except Exception as e:
            # На старых SQLite могут быть ограничения, просто логируем
            logger.debug(f"ensure timezone column: {e}")


async def _ensure_reminders_columns():
    """Гарантирует наличие новых столбцов/индексов в reminders для цепочек и идемпотентности."""
    async with get_conn() as db:
        try:
            cur = await db.execute("PRAGMA table_info(reminders)")
            cols = await cur.fetchall()
            col_names = {c[1] for c in cols}
            to_add = []
            if "picked_at" not in col_names:
                to_add.append(("picked_at", "DATETIME"))
            if "fired_at" not in col_names:
                to_add.append(("fired_at", "DATETIME"))
            if "idempotency_key" not in col_names:
                to_add.append(("idempotency_key", "TEXT"))
            if "meta_json" not in col_names:
                to_add.append(("meta_json", "TEXT"))
            for name, typ in to_add:
                try:
                    await db.execute(f"ALTER TABLE reminders ADD COLUMN {name} {typ}")
                except Exception as e:
                    logger.debug(f"alter reminders add {name}: {e}")
            # Перечитаем список колонок после ALTER
            cur = await db.execute("PRAGMA table_info(reminders)")
            cols2 = await cur.fetchall()
            col_names2 = {c[1] for c in cols2}
            # Индексы по reminders
            try:
                await db.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due_status ON reminders(status, due_at)")
            except Exception:
                pass
            try:
                await db.execute("CREATE INDEX IF NOT EXISTS idx_reminders_chat ON reminders(chat_id)")
            except Exception:
                pass
            # Индекс идемпотентности (создаём только если есть столбец)
            if "idempotency_key" in col_names2:
                try:
                    await db.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_reminders_idemp ON reminders(idempotency_key) WHERE idempotency_key IS NOT NULL"
                    )
                except Exception as e:
                    logger.debug(f"create index reminders idemp: {e}")
            await db.commit()
        except Exception as e:
            logger.debug(f"ensure reminders columns: {e}")


async def _ensure_self_calls_table():
    """Создаёт таблицу self_calls для самовызовов ассистента, если её нет."""
    async with get_conn() as db:
        try:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS self_calls (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id         INTEGER NOT NULL,
                    user_id         INTEGER NOT NULL,
                    due_at          DATETIME NOT NULL,   -- UTC
                    topic           TEXT,
                    payload_json    TEXT,
                    status          TEXT DEFAULT 'scheduled',
                    picked_at       DATETIME,
                    fired_at        DATETIME,
                    executed_at     DATETIME,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_self_calls_due_status ON self_calls(status, due_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_self_calls_chat ON self_calls(chat_id)")
            await db.commit()
        except Exception as e:
            logger.debug(f"ensure self_calls table: {e}")


async def init_db():
    """Применяет schema.sql ровно один раз, потокобезопасно."""
    global _schema_applied
    if _schema_applied:
        return
    async with _schema_lock:
        if _schema_applied:
            return
        try:
            schema_path = Path(__file__).parent.parent.parent / "schema.sql"
            if not schema_path.exists():
                raise FileNotFoundError(f"Schema file not found: {schema_path}")
            sql_script = schema_path.read_text(encoding="utf-8-sig")
            async with get_conn() as db:
                await db.executescript(sql_script)
                await db.commit()
            # Миграции
            await _ensure_users_timezone_column()
            await _ensure_reminders_columns()
            await _ensure_self_calls_table()
            _schema_applied = True
            logger.debug("↪️  Schema applied")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise


async def save_user(user: User) -> bool:
    """Сохраняет информацию о пользователе. Возвращает True, если пользователь новый."""
    async with get_conn() as db:
        # Проверяем, есть ли уже пользователь
        cur = await db.execute(
            "SELECT is_welcomed FROM users WHERE user_id = ?",
            (user.id,),
        )
        existing = await cur.fetchone()

        if existing is None:
            # Новый пользователь
            await db.execute(
                """INSERT INTO users (user_id, username, first_name, last_name, is_welcomed) 
                   VALUES (?, ?, ?, ?, FALSE)""",
                (user.id, user.username, user.first_name, user.last_name),
            )
            await db.commit()
            return True  # Новый пользователь
        else:
            # Обновляем информацию существующего пользователя
            await db.execute(
                """UPDATE users SET username = ?, first_name = ?, last_name = ? 
                   WHERE user_id = ?""",
                (user.username, user.first_name, user.last_name, user.id),
            )
            await db.commit()
            return not existing[0]  # Возвращаем True, если еще не приветствовали


async def mark_user_welcomed(user_id: int):
    """Отмечает, что пользователь получил приветственное сообщение."""
    async with get_conn() as db:
        await db.execute(
            "UPDATE users SET is_welcomed = TRUE WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def get_user_display_name(user_id: int) -> str:
    """Получает отображаемое имя пользователя."""
    async with get_conn() as db:
        cur = await db.execute(
            "SELECT username, first_name, last_name FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()

        if row:
            username, first_name, last_name = row
            if username:
                return f"@{username}"
            elif first_name and last_name:
                return f"{first_name} {last_name}"
            elif first_name:
                return first_name
            else:
                return str(user_id)
        else:
            return str(user_id)


async def save_openai_file_id(chat_id: int, file_id: str):
    """Сохраняет file_id загруженного в OpenAI файла для чата."""
    async with get_conn() as db:
        await db.execute(
            "INSERT INTO openai_files (chat_id, file_id) VALUES (?, ?)",
            (chat_id, file_id),
        )
        await db.commit()


async def get_openai_file_ids_by_chat(chat_id: int) -> list[str]:
    """Возвращает список file_id для данного чата."""
    async with get_conn() as db:
        cur = await db.execute(
            "SELECT file_id FROM openai_files WHERE chat_id = ?",
            (chat_id,),
        )
        rows = await cur.fetchall()
        return [row[0] for row in rows]


async def delete_openai_file_ids_by_chat(chat_id: int):
    """Удаляет все file_id для данного чата из таблицы openai_files."""
    async with get_conn() as db:
        await db.execute(
            "DELETE FROM openai_files WHERE chat_id = ?",
            (chat_id,),
        )
        await db.commit()


async def get_user_timezone(user_id: int) -> str:
    """Возвращает таймзону пользователя (IANA, например 'Europe/Moscow').
    Если столбца/значения нет — возвращает дефолт 'Europe/Moscow'."""
    default_tz = "Europe/Moscow"
    async with get_conn() as db:
        try:
            cur = await db.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            if row and row[0]:
                return str(row[0])
            return default_tz
        except Exception:
            # Столбца timezone может не быть
            return default_tz


async def get_user_timezone_or_none(user_id: int) -> str | None:
    """Возвращает таймзону пользователя или None, если не задана/столбца нет."""
    async with get_conn() as db:
        try:
            cur = await db.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            if row and row[0]:
                return str(row[0])
            return None
        except Exception:
            return None


async def set_user_timezone(user_id: int, tz_name: str) -> bool:
    """Устанавливает таймзону пользователя. Возвращает True при успехе."""
    # Валидация
    try:
        pytz.timezone(tz_name)
    except Exception:
        return False
    async with get_conn() as db:
        await db.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (tz_name, user_id))
        await db.commit()
    return True


async def close_pool():
    """Закрывает все соединения в пуле (вызывать при завершении приложения)."""
    async with _pool_lock:
        while _connection_pool:
            db = _connection_pool.pop()
            await db.close()
