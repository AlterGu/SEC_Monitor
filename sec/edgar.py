import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


@dataclass
class Filing:
    accession_no: str
    form_type: str
    filed_date: str
    company_name: str
    description: str
    filing_url: str
    document_url: str


class EdgarClient:
    def __init__(self):
        self._headers = {"User-Agent": config.USER_AGENT}
        self._ticker_cache: dict[str, tuple[str, str]] = {}  # ticker -> (cik, name)

    async def _get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(headers=self._headers)

    async def get_cik(self, ticker: str) -> tuple[str, str]:
        """Get CIK and company name from ticker symbol."""
        ticker = ticker.upper()
        if ticker in self._ticker_cache:
            return self._ticker_cache[ticker]

        async with await self._get_session() as session:
            async with session.get(COMPANY_TICKERS_URL) as resp:
                logger.info(f"SEC tickers API status: {resp.status}")
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"SEC tickers API error: {text[:500]}")
                    raise ValueError(f"SEC API returned status {resp.status}")
                data = await resp.json()

        logger.info(f"Loaded {len(data)} tickers from SEC, searching for '{ticker}'")

        for entry in data.values():
            if entry["ticker"].upper() == ticker:
                cik = str(entry["cik_str"]).zfill(10)
                name = entry["title"]
                self._ticker_cache[ticker] = (cik, name)
                logger.info(f"Found ticker {ticker}: CIK={cik}, name={name}")
                return cik, name

        # Show a few sample tickers for debugging
        sample = [e["ticker"] for e in list(data.values())[:5]]
        logger.error(f"Ticker '{ticker}' not found. Sample tickers: {sample}")
        raise ValueError(f"Ticker '{ticker}' not found on SEC EDGAR")

    async def get_latest_filings(
        self,
        cik: str,
        form_types: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[Filing]:
        """Get recent filings for a company by CIK."""
        if form_types is None:
            form_types = config.DEFAULT_FORM_TYPES
        if since is None:
            since = datetime.now() - timedelta(days=7)

        url = COMPANY_SUBMISSIONS_URL.format(cik=cik)

        async with await self._get_session() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()

        company_name = data.get("name", "Unknown")
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        descriptions = recent.get("primaryDocDescription", [])
        primary_docs = recent.get("primaryDocument", [])

        filings = []
        since_str = since.strftime("%Y-%m-%d")

        for i in range(len(forms)):
            if forms[i] not in form_types:
                continue
            if dates[i] < since_str:
                continue

            accession_raw = accessions[i]
            accession_no = accession_raw.replace("-", "")
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_no}/{accession_raw}-index.html"
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_no}/{primary_docs[i]}"

            filings.append(
                Filing(
                    accession_no=accession_raw,
                    form_type=forms[i],
                    filed_date=dates[i],
                    company_name=company_name,
                    description=descriptions[i] if i < len(descriptions) else "",
                    filing_url=filing_url,
                    document_url=doc_url,
                )
            )

            if len(filings) >= limit:
                break

        return filings

    async def get_filing_content(self, url: str) -> str:
        """Fetch and extract text content from a filing document."""
        async with await self._get_session() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "")

                if "xml" in content_type or url.endswith(".xml"):
                    # XML documents: parse with XML parser for reliability
                    raw = await resp.text()
                    soup = BeautifulSoup(raw, "xml")
                    text = soup.get_text(separator="\n", strip=True)
                elif "html" in content_type or url.endswith((".htm", ".html")):
                    html = await resp.text()
                    soup = BeautifulSoup(html, "lxml")
                    # Remove script and style elements
                    for tag in soup(["script", "style"]):
                        tag.decompose()
                    text = soup.get_text(separator="\n", strip=True)
                else:
                    text = await resp.text()

        # Truncate to avoid exceeding OpenAI token limits
        if len(text) > config.MAX_SUMMARY_CHARS:
            text = text[:config.MAX_SUMMARY_CHARS] + "\n\n[Content truncated...]"

        return text

    async def get_filing_index_url(self, cik: str, accession_no: str) -> str:
        """Get the filing index page URL."""
        cik_num = cik.lstrip("0")
        acc_clean = accession_no.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{acc_clean}/{accession_no}-index.html"
