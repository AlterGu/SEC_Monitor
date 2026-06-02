import logging

from supabase import create_client, Client

from db.base import DatabaseBackend

logger = logging.getLogger(__name__)


class SupabaseBackend(DatabaseBackend):
    def __init__(self, url: str, key: str):
        self._client: Client = create_client(url, key)

    async def init(self):
        logger.info("Supabase backend connected (tables must be created manually)")

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
