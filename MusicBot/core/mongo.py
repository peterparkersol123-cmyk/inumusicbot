import aiosqlite
import json
import logging
import os

LOGGER = logging.getLogger("MusicBot.DB")

DB_PATH = os.getenv("DB_PATH", "/data/musicbot.db")


class MongoDB:
    """SQLite-backed store. Same interface as the old MongoDB class."""

    def __init__(self):
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS auth (
                chat_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS sudoers (
                user_id INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY (chat_id, key)
            );
        """)
        await self._db.commit()
        LOGGER.info(f"SQLite connected: {DB_PATH}")

    async def close(self):
        if self._db:
            await self._db.close()
            LOGGER.info("SQLite disconnected.")

    # --- Auth ---
    async def add_auth(self, chat_id: int, user_id: int):
        await self._db.execute(
            "INSERT OR IGNORE INTO auth (chat_id, user_id) VALUES (?, ?)",
            (chat_id, user_id),
        )
        await self._db.commit()

    async def remove_auth(self, chat_id: int, user_id: int):
        await self._db.execute(
            "DELETE FROM auth WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        await self._db.commit()

    async def get_auth(self, chat_id: int) -> list[int]:
        async with self._db.execute(
            "SELECT user_id FROM auth WHERE chat_id = ?", (chat_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [r["user_id"] for r in rows]

    # --- Sudoers ---
    async def add_sudo(self, user_id: int):
        await self._db.execute(
            "INSERT OR IGNORE INTO sudoers (user_id) VALUES (?)", (user_id,)
        )
        await self._db.commit()

    async def remove_sudo(self, user_id: int):
        await self._db.execute(
            "DELETE FROM sudoers WHERE user_id = ?", (user_id,)
        )
        await self._db.commit()

    async def get_sudoers(self) -> list[int]:
        async with self._db.execute("SELECT user_id FROM sudoers") as cur:
            rows = await cur.fetchall()
        return [r["user_id"] for r in rows]

    # --- Settings ---
    async def set_setting(self, chat_id: int, key: str, value):
        await self._db.execute(
            "INSERT OR REPLACE INTO settings (chat_id, key, value) VALUES (?, ?, ?)",
            (chat_id, key, json.dumps(value)),
        )
        await self._db.commit()

    async def get_setting(self, chat_id: int, key: str, default=None):
        async with self._db.execute(
            "SELECT value FROM settings WHERE chat_id = ? AND key = ?",
            (chat_id, key),
        ) as cur:
            row = await cur.fetchone()
        if row:
            return json.loads(row["value"])
        return default
