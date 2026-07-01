import logging
from html import escape

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from bot.messaging import send_long_message
from bot.scheduler import sync_jobs
from db import database
from sec.edgar import EdgarClient
from summarizer.openai_summarizer import summarize_filing

logger = logging.getLogger(__name__)

edgar = EdgarClient()


def _is_authorized(user_id: int) -> bool:
    """Check if a user is authorized via whitelist."""
    return not config.ALLOWED_USER_IDS or user_id in config.ALLOWED_USER_IDS


async def _needs_password(user_id: int) -> bool:
    """Check if a user needs to enter a password."""
    if not config.ACCESS_PASSWORD or config.ALLOWED_USER_IDS:
        return False
    return not await database.is_user_verified(user_id)


async def _check_access(update: Update) -> bool:
    """Check access and send rejection message if denied. Returns True if allowed."""
    user_id = update.effective_user.id

    if not _is_authorized(user_id):
        await update.message.reply_text("Access denied. Your user ID is not in the whitelist.")
        return False

    if await _needs_password(user_id):
        await update.message.reply_text("Please enter the access password:")
        return False

    return True


async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle password input from unauthenticated users."""
    if not await _needs_password(update.effective_user.id):
        return

    if update.message.text == config.ACCESS_PASSWORD:
        await database.mark_user_verified(update.effective_user.id)
        await update.message.reply_text("Password correct. You now have access.\n\nUse /start to see available commands.")
        logger.info(f"User {update.effective_user.id} authenticated via password")
    else:
        await update.message.reply_text("Wrong password. Try again:")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_access(update):
        return

    await update.message.reply_text(
        "📊 *SEC Monitor Bot*\n\n"
        "I monitor SEC filings for your stocks and send summaries.\n\n"
        "<b>Commands:</b>\n"
        "/monitor &lt;TICKER&gt; - Start monitoring a stock\n"
        "/unmonitor &lt;TICKER&gt; - Stop monitoring\n"
        "/list - Show your monitored stocks\n"
        "/check &lt;TICKER&gt; - Check for new filings now\n"
        "/interval &lt;MINUTES&gt; - Set check interval (default: 240)\n\n"
        "Example: <code>/monitor RKLB</code>",
        parse_mode="HTML",
    )


async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_access(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /monitor <TICKER>\nExample: /monitor RKLB")
        return

    ticker = context.args[0].upper()
    user_id = update.effective_user.id

    try:
        cik, company_name = await edgar.get_cik(ticker)
    except ValueError:
        await update.message.reply_text(f"❌ Ticker '{ticker}' not found on SEC EDGAR.")
        return

    interval = config.DEFAULT_INTERVAL_MINUTES
    await database.add_subscription(user_id, ticker, cik, company_name, interval)

    await update.message.reply_text(
        f"✅ Now monitoring <b>{company_name}</b> (<code>{ticker}</code>)\n"
        f"Checking every {interval} minutes.\n"
        f"Use /check {ticker} to check now.",
        parse_mode="HTML",
    )

    await sync_jobs(context.application)
    await _check_and_notify(update, context, user_id, ticker, cik, company_name)


async def unmonitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_access(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /unmonitor <TICKER>")
        return

    ticker = context.args[0].upper()
    user_id = update.effective_user.id

    removed = await database.remove_subscription(user_id, ticker)
    if removed:
        await update.message.reply_text(f"✅ Stopped monitoring <code>{ticker}</code>.", parse_mode="HTML")
        await sync_jobs(context.application)
    else:
        await update.message.reply_text(f"❌ You weren't monitoring <code>{ticker}</code>.", parse_mode="HTML")


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_access(update):
        return

    user_id = update.effective_user.id
    subs = await database.get_subscriptions(user_id)

    if not subs:
        await update.message.reply_text("You're not monitoring any stocks.\nUse /monitor <TICKER> to start.")
        return

    lines = ["📊 <b>Your monitored stocks:</b>\n"]
    for sub in subs:
        lines.append(
            f"• <code>{sub['ticker']}</code> - {sub['company_name']} (every {sub['interval_minutes']}m)"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_access(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /check <TICKER>")
        return

    ticker = context.args[0].upper()
    user_id = update.effective_user.id

    subs = await database.get_subscriptions(user_id)
    sub = next((s for s in subs if s["ticker"] == ticker), None)

    if not sub:
        await update.message.reply_text(f"❌ You're not monitoring <code>{ticker}</code>. Use /monitor first.", parse_mode="HTML")
        return

    await update.message.reply_text(f"🔍 Checking {ticker}...")
    await _check_and_notify(update, context, user_id, ticker, sub["cik"], sub["company_name"])


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_access(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /interval <MINUTES>\nExample: /interval 30")
        return

    try:
        minutes = int(context.args[0])
        if minutes < 5 or minutes > 1440:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Interval must be between 5 and 1440 minutes.")
        return

    user_id = update.effective_user.id
    subs = await database.get_subscriptions(user_id)

    if not subs:
        await update.message.reply_text("❌ No active subscriptions. Use /monitor first.")
        return

    for sub in subs:
        await database.update_interval(user_id, sub["ticker"], minutes)

    await update.message.reply_text(f"✅ Check interval set to {minutes} minutes for all subscriptions.")
    await sync_jobs(context.application)


async def _check_and_notify(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    ticker: str,
    cik: str,
    company_name: str,
):
    """Check for new filings and notify user."""
    try:
        filings = await edgar.get_latest_filings(cik, since=None, limit=10)
    except Exception as e:
        logger.error(f"Failed to fetch filings for {ticker}: {e}")
        await update.message.reply_text(f"❌ Error fetching filings for {ticker}: {e}")
        return

    new_filings = []
    for f in filings:
        if not await database.is_filing_seen(user_id, f.accession_no):
            new_filings.append(f)

    if not new_filings:
        await update.message.reply_text(f"No new SEC filings for {ticker}.")
        return

    await update.message.reply_text(f"📬 Found {len(new_filings)} new filing(s) for {ticker}...")

    for filing in new_filings:
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
            f"📝 <b>Summary:</b>\n{summary}"
        )

        await send_long_message(context.bot, user_id, message)

        await database.mark_filing_seen(user_id, filing.accession_no, ticker)


def get_handlers() -> list:
    """Return all command handlers."""
    return [
        CommandHandler("start", start),
        CommandHandler("monitor", monitor),
        CommandHandler("unmonitor", unmonitor),
        CommandHandler("list", list_subscriptions),
        CommandHandler("check", check),
        CommandHandler("interval", set_interval),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password),
    ]
