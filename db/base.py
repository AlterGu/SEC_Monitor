from abc import ABC, abstractmethod


class DatabaseBackend(ABC):
    """Abstract database interface."""

    @abstractmethod
    async def init(self):
        """Initialize database / create tables."""
        ...

    @abstractmethod
    async def close(self):
        """Close database connection."""
        ...

    @abstractmethod
    async def add_subscription(
        self, user_id: int, ticker: str, cik: str, company_name: str, interval: int
    ):
        ...

    @abstractmethod
    async def remove_subscription(self, user_id: int, ticker: str) -> bool:
        ...

    @abstractmethod
    async def get_subscriptions(self, user_id: int) -> list[dict]:
        ...

    @abstractmethod
    async def get_all_active_subscriptions(self) -> list[dict]:
        ...

    @abstractmethod
    async def update_interval(self, user_id: int, ticker: str, interval: int) -> bool:
        ...

    @abstractmethod
    async def is_filing_seen(self, user_id: int, accession_no: str) -> bool:
        ...

    @abstractmethod
    async def mark_filing_seen(self, user_id: int, accession_no: str, ticker: str = ""):
        ...

    @abstractmethod
    async def is_user_verified(self, user_id: int) -> bool:
        ...

    @abstractmethod
    async def mark_user_verified(self, user_id: int):
        ...
