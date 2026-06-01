import logging
from pathlib import Path

import aiosqlite

import config

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(config.DB_PATH)
        _db.row_factory = aiosqlite.Row
    return _db


async def init_db():
    db = await get_db()
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

        CREATE INDEX IF NOT EXISTS idx_seen_user_acc
            ON seen_filings(user_id, accession_no);
        CREATE INDEX IF NOT EXISTS idx_sub_user
            ON subscriptions(user_id);
        """
    )
    await db.commit()
    logger.info("Database initialized")


async def add_subscription(
    user_id: int, ticker: str, cik: str, company_name: str, interval: int
):
    db = await get_db()
    await db.execute(
        """
        INSERT OR REPLACE INTO subscriptions (user_id, ticker, cik, company_name, interval_minutes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, ticker.upper(), cik, company_name, interval),
    )
    await db.commit()


async def remove_subscription(user_id: int, ticker: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM subscriptions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_subscriptions(user_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_active_subscriptions() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM subscriptions ORDER BY user_id, ticker")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_interval(user_id: int, ticker: str, interval: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE subscriptions SET interval_minutes = ? WHERE user_id = ? AND ticker = ?",
        (interval, user_id, ticker.upper()),
    )
    await db.commit()
    return cursor.rowcount > 0


async def is_filing_seen(user_id: int, accession_no: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT 1 FROM seen_filings WHERE user_id = ? AND accession_no = ?",
        (user_id, accession_no),
    )
    return await cursor.fetchone() is not None


async def mark_filing_seen(user_id: int, accession_no: str, ticker: str = ""):
    db = await get_db()
    await db.execute(
        """
        INSERT OR IGNORE INTO seen_filings (user_id, accession_no, ticker)
        VALUES (?, ?, ?)
        """,
        (user_id, accession_no, ticker),
    )
    await db.commit()


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
