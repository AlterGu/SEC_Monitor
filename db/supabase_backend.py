import logging

import asyncpg
from supabase import create_client, Client

import config
from db.base import DatabaseBackend

logger = logging.getLogger(__name__)

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    ticker TEXT NOT NULL,
    cik TEXT NOT NULL,
    company_name TEXT NOT NULL DEFAULT '',
    interval_minutes INT NOT NULL DEFAULT 60,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS seen_filings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    accession_no TEXT NOT NULL,
    ticker TEXT NOT NULL DEFAULT '',
    seen_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, accession_no)
);

CREATE TABLE IF NOT EXISTS verified_users (
    user_id BIGINT PRIMARY KEY,
    verified_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seen_user_acc ON seen_filings(user_id, accession_no);
CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id);
"""

_EXPECTED_TABLES = {"subscriptions", "seen_filings", "verified_users"}


class SupabaseBackend(DatabaseBackend):
    def __init__(self, url: str, key: str):
        self._client: Client = create_client(url, key)

    async def init(self):
        if not config.SUPABASE_DB_URL:
            logger.warning(
                "SUPABASE_DB_URL not set - cannot auto-create tables. "
                "Tables must exist in Supabase. See README for SQL schema."
            )
            return

        conn = None
        try:
            conn = await asyncpg.connect(config.SUPABASE_DB_URL)

            # Check which tables exist
            rows = await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY($1)",
                list(_EXPECTED_TABLES),
            )
            existing = {r["table_name"] for r in rows}
            missing = _EXPECTED_TABLES - existing

            if missing:
                logger.info(f"Missing tables: {missing}. Creating...")
                await conn.execute(_TABLES_SQL)
                logger.info("All tables created successfully")
            else:
                logger.info("All required tables exist")

                # Check columns for each table
                for table in _EXPECTED_TABLES:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = $1",
                        table,
                    )
                    col_names = {r["column_name"] for r in cols}
                    logger.debug(f"Table '{table}' columns: {col_names}")

        except Exception as e:
            logger.error(f"Failed to check/create Supabase tables: {e}")
            # Still try to run CREATE TABLE IF NOT EXISTS as fallback
            if conn:
                try:
                    await conn.execute(_TABLES_SQL)
                    logger.info("Fallback table creation succeeded")
                except Exception as e2:
                    logger.error(f"Fallback table creation also failed: {e2}")
        finally:
            if conn:
                await conn.close()

    async def close(self):
        pass

    async def add_subscription(
        self, user_id: int, ticker: str, cik: str, company_name: str, interval: int
    ):
        self._client.table("subscriptions").upsert(
            {
                "user_id": user_id,
                "ticker": ticker.upper(),
                "cik": cik,
                "company_name": company_name,
                "interval_minutes": interval,
            },
            on_conflict="user_id,ticker",
        ).execute()

    async def remove_subscription(self, user_id: int, ticker: str) -> bool:
        resp = (
            self._client.table("subscriptions")
            .delete()
            .eq("user_id", user_id)
            .eq("ticker", ticker.upper())
            .execute()
        )
        return len(resp.data) > 0

    async def get_subscriptions(self, user_id: int) -> list[dict]:
        resp = (
            self._client.table("subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .order("ticker")
            .execute()
        )
        return resp.data

    async def get_all_active_subscriptions(self) -> list[dict]:
        resp = (
            self._client.table("subscriptions")
            .select("*")
            .order("user_id")
            .order("ticker")
            .execute()
        )
        return resp.data

    async def update_interval(self, user_id: int, ticker: str, interval: int) -> bool:
        resp = (
            self._client.table("subscriptions")
            .update({"interval_minutes": interval})
            .eq("user_id", user_id)
            .eq("ticker", ticker.upper())
            .execute()
        )
        return len(resp.data) > 0

    async def is_filing_seen(self, user_id: int, accession_no: str) -> bool:
        resp = (
            self._client.table("seen_filings")
            .select("id")
            .eq("user_id", user_id)
            .eq("accession_no", accession_no)
            .limit(1)
            .execute()
        )
        return len(resp.data) > 0

    async def mark_filing_seen(self, user_id: int, accession_no: str, ticker: str = ""):
        self._client.table("seen_filings").upsert(
            {
                "user_id": user_id,
                "accession_no": accession_no,
                "ticker": ticker,
            },
            on_conflict="user_id,accession_no",
        ).execute()

    async def is_user_verified(self, user_id: int) -> bool:
        resp = (
            self._client.table("verified_users")
            .select("user_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return len(resp.data) > 0

    async def mark_user_verified(self, user_id: int):
        self._client.table("verified_users").upsert(
            {"user_id": user_id},
            on_conflict="user_id",
        ).execute()
