"""Оптимизированная обёртка над aiosqlite с пулом соединений."""
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
import logging
from aiogram.types import User
import asyncio

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


async def init_db():
    """Выполняет schema.sql при первом запуске."""
    try:
        schema_path = Path(__file__).parent.parent.parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        # Читаем файл в utf-8-sig чтобы корректо обработать BOM
        sql_script = schema_path.read_text(encoding="utf-8-sig")

        async with get_conn() as db:
            await db.executescript(sql_script)
            await db.commit()
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