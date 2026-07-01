import logging
from datetime import datetime, timedelta
from html import escape

from telegram.ext import Application, ContextTypes

from db import database
from bot.messaging import send_long_message
from sec.edgar import EdgarClient
from summarizer.openai_summarizer import summarize_filing

logger = logging.getLogger(__name__)

edgar = EdgarClient()


async def check_user_ticker(context: ContextTypes.DEFAULT_TYPE):
    """Job callback: check one user's ticker for new filings."""
    job_data = context.job.data
    user_id = job_data["user_id"]
    ticker = job_data["ticker"]
    cik = job_data["cik"]
    company_name = job_data["company_name"]

    logger.info(f"Checking {ticker} for user {user_id}")

    try:
        interval = job_data.get("interval_minutes", 60)
        since = datetime.now() - timedelta(minutes=interval * 2)
        filings = await edgar.get_latest_filings(cik, since=since, limit=10)
    except Exception as e:
        logger.error(f"Failed to fetch filings for {ticker}: {e}")
        return

    for filing in filings:
        if await database.is_filing_seen(user_id, filing.accession_no):
            continue

        try:
            content = await edgar.get_filing_content(filing.document_url)
            summary = await summarize_filing(content, filing.form_type, filing.company_name)
        except Exception as e:
            logger.warning(f"Failed to summarize {filing.accession_no}: {e}")
            summary = f"Could not generate summary: {e}"

        message = (
            f"🔔 <b>SEC Filing Alert: {escape(ticker)}</b>\n\n"
            f"📋 <b>Form:</b> {escape(filing.form_type)}\n"
            f"🏢 <b>Company:</b> {escape(filing.company_name)}\n"
            f"📅 <b>Filed:</b> {escape(filing.filed_date)}\n"
            f"🔗 <b>Filing:</b> <a href=\"{filing.filing_url}\">View on SEC</a>\n"
            f"📄 <b>Document:</b> <a href=\"{filing.document_url}\">Read Full</a>\n\n"
            f"📝 <b>Summary:</b>\n{escape(summary)}"
        )

        await send_long_message(context.bot, user_id, message)

        await database.mark_filing_seen(user_id, filing.accession_no, ticker)


def _job_id(user_id: int, ticker: str) -> str:
    return f"sec_check_{user_id}_{ticker}"


async def sync_jobs(app: Application):
    """Sync job queue with database subscriptions."""
    subs = await database.get_all_active_subscriptions()
    active_keys = {(s["user_id"], s["ticker"]) for s in subs}

    # Remove stale jobs
    for job in app.job_queue.jobs():
        if job.id.startswith("sec_check_"):
            parts = job.id.split("_", 3)
            user_id = int(parts[2])
            ticker = parts[3]
            if (user_id, ticker) not in active_keys:
                job.schedule_removal()
                logger.info(f"Removed stale job {job.id}")

    # Add/update jobs
    for sub in subs:
        job_id = _job_id(sub["user_id"], sub["ticker"])
        interval_sec = sub["interval_minutes"] * 60

        # Remove existing job first
        current_jobs = app.job_queue.get_jobs_by_name(job_id)
        for j in current_jobs:
            j.schedule_removal()

        app.job_queue.run_repeating(
            check_user_ticker,
            interval=interval_sec,
            first=10,  # Start 10s after sync
            name=job_id,
            data={
                "user_id": sub["user_id"],
                "ticker": sub["ticker"],
                "cik": sub["cik"],
                "company_name": sub["company_name"],
                "interval_minutes": sub["interval_minutes"],
            },
        )
        logger.info(
            f"Scheduled job for {sub['ticker']} (user {sub['user_id']}) every {sub['interval_minutes']}m"
        )


async def startup_sync(app: Application):
    """Called once on bot startup to load existing subscriptions."""
    await sync_jobs(app)
