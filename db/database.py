import logging

import config
from db.base import DatabaseBackend

logger = logging.getLogger(__name__)

_backend: DatabaseBackend | None = None


def _get_backend() -> DatabaseBackend:
    global _backend
    if _backend is None:
        if config.DB_BACKEND == "supabase":
            from db.supabase_backend import SupabaseBackend

            if not config.SUPABASE_URL or not config.SUPABASE_KEY:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set for supabase backend")
            _backend = SupabaseBackend(config.SUPABASE_URL, config.SUPABASE_KEY)
            logger.info("Using Supabase backend")
        else:
            from db.sqlite_backend import SQLiteBackend

            _backend = SQLiteBackend(config.DB_PATH)
            logger.info("Using SQLite backend")
    return _backend


async def init_db():
    await _get_backend().init()


async def close_db():
    if _backend:
        await _backend.close()


async def add_subscription(
    user_id: int, ticker: str, cik: str, company_name: str, interval: int
):
    await _get_backend().add_subscription(user_id, ticker, cik, company_name, interval)


async def remove_subscription(user_id: int, ticker: str) -> bool:
    return await _get_backend().remove_subscription(user_id, ticker)


async def get_subscriptions(user_id: int) -> list[dict]:
    return await _get_backend().get_subscriptions(user_id)


async def get_all_active_subscriptions() -> list[dict]:
    return await _get_backend().get_all_active_subscriptions()


async def update_interval(user_id: int, ticker: str, interval: int) -> bool:
    return await _get_backend().update_interval(user_id, ticker, interval)


async def is_filing_seen(user_id: int, accession_no: str) -> bool:
    return await _get_backend().is_filing_seen(user_id, accession_no)


async def mark_filing_seen(user_id: int, accession_no: str, ticker: str = ""):
    await _get_backend().mark_filing_seen(user_id, accession_no, ticker)
