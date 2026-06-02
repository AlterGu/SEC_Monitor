import logging
from pathlib import Path

import aiosqlite

from db.base import DatabaseBackend

logger = logging.getLogger(__name__)


class SQLiteBackend(DatabaseBackend):
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._db is None:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
        return self._db

    async def init(self):
        db = await self._get_conn()
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                cik TEXT NOT NULL,
                company_name TEXT NOT NULL DEFAULT '',
                interval_minutes INTEGER NOT NULL DEFAULT 60,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, ticker)
            );

            CREATE TABLE IF NOT EXISTS seen_filings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                accession_no TEXT NOT NULL,
                ticker TEXT NOT NULL DEFAULT '',
                seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, accession_no)
            );

            CREATE TABLE IF NOT EXISTS verified_users (
                user_id INTEGER PRIMARY KEY,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_seen_user_acc
                ON seen_filings(user_id, accession_no);
            CREATE INDEX IF NOT EXISTS idx_sub_user
                ON subscriptions(user_id);
            """
        )
        await db.commit()
        logger.info("SQLite database initialized")

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    async def add_subscription(
        self, user_id: int, ticker: str, cik: str, company_name: str, interval: int
    ):
        db = await self._get_conn()
        await db.execute(
            """
            INSERT OR REPLACE INTO subscriptions (user_id, ticker, cik, company_name, interval_minutes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, ticker.upper(), cik, company_name, interval),
        )
        await db.commit()

    async def remove_subscription(self, user_id: int, ticker: str) -> bool:
        db = await self._get_conn()
        cursor = await db.execute(
            "DELETE FROM subscriptions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def get_subscriptions(self, user_id: int) -> list[dict]:
        db = await self._get_conn()
        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_active_subscriptions(self) -> list[dict]:
        db = await self._get_conn()
        cursor = await db.execute("SELECT * FROM subscriptions ORDER BY user_id, ticker")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_interval(self, user_id: int, ticker: str, interval: int) -> bool:
        db = await self._get_conn()
        cursor = await db.execute(
            "UPDATE subscriptions SET interval_minutes = ? WHERE user_id = ? AND ticker = ?",
            (interval, user_id, ticker.upper()),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def is_filing_seen(self, user_id: int, accession_no: str) -> bool:
        db = await self._get_conn()
        cursor = await db.execute(
            "SELECT 1 FROM seen_filings WHERE user_id = ? AND accession_no = ?",
            (user_id, accession_no),
        )
        return await cursor.fetchone() is not None

    async def mark_filing_seen(self, user_id: int, accession_no: str, ticker: str = ""):
        db = await self._get_conn()
        await db.execute(
            """
            INSERT OR IGNORE INTO seen_filings (user_id, accession_no, ticker)
            VALUES (?, ?, ?)
            """,
            (user_id, accession_no, ticker),
        )
        await db.commit()

    async def is_user_verified(self, user_id: int) -> bool:
        db = await self._get_conn()
        cursor = await db.execute(
            "SELECT 1 FROM verified_users WHERE user_id = ?",
            (user_id,),
        )
        return await cursor.fetchone() is not None

    async def mark_user_verified(self, user_id: int):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR IGNORE INTO verified_users (user_id) VALUES (?)",
            (user_id,),
        )
        await db.commit()
