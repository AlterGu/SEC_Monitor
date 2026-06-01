import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

import config
from bot.scheduler import sync_jobs
from db import database
from sec.edgar import EdgarClient
from summarizer.openai_summarizer import summarize_filing

logger = logging.getLogger(__name__)

edgar = EdgarClient()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *SEC Monitor Bot*\n\n"
        "I monitor SEC filings for your stocks and send summaries.\n\n"
        "*Commands:*\n"
        "/monitor <TICKER> - Start monitoring a stock\n"
        "/unmonitor <TICKER> - Stop monitoring\n"
        "/list - Show your monitored stocks\n"
        "/check <TICKER> - Check for new filings now\n"
        "/interval <MINUTES> - Set check interval (default: 60)\n\n"
        "Example: `/monitor RKLB`",
        parse_mode="Markdown",
    )


async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        f"✅ Now monitoring *{company_name}* (`{ticker}`)\n"
        f"Checking every {interval} minutes.\n"
        f"Use /check {ticker} to check now.",
        parse_mode="Markdown",
    )

    # Sync scheduler to pick up new subscription
    await sync_jobs(context.application)

    # Immediately check for recent filings
    await _check_and_notify(update, context, user_id, ticker, cik, company_name)


async def unmonitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unmonitor <TICKER>")
        return

    ticker = context.args[0].upper()
    user_id = update.effective_user.id

    removed = await database.remove_subscription(user_id, ticker)
    if removed:
        await update.message.reply_text(f"✅ Stopped monitoring `{ticker}`.", parse_mode="Markdown")
        await sync_jobs(context.application)
    else:
        await update.message.reply_text(f"❌ You weren't monitoring `{ticker}`.", parse_mode="Markdown")


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subs = await database.get_subscriptions(user_id)

    if not subs:
        await update.message.reply_text("You're not monitoring any stocks.\nUse /monitor <TICKER> to start.")
        return

    lines = ["📊 *Your monitored stocks:*\n"]
    for sub in subs:
        lines.append(
            f"• `{sub['ticker']}` - {sub['company_name']} (every {sub['interval_minutes']}m)"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /check <TICKER>")
        return

    ticker = context.args[0].upper()
    user_id = update.effective_user.id

    subs = await database.get_subscriptions(user_id)
    sub = next((s for s in subs if s["ticker"] == ticker), None)

    if not sub:
        await update.message.reply_text(f"❌ You're not monitoring `{ticker}`. Use /monitor first.", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🔍 Checking {ticker}...")
    await _check_and_notify(update, context, user_id, ticker, sub["cik"], sub["company_name"])


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            f"🔔 *SEC Filing Alert: {ticker}*\n\n"
            f"📋 *Form:* {filing.form_type}\n"
            f"🏢 *Company:* {filing.company_name}\n"
            f"📅 *Filed:* {filing.filed_date}\n"
            f"🔗 *Filing:* [View on SEC]({filing.filing_url})\n"
            f"📄 *Document:* [Read Full]({filing.document_url})\n\n"
            f"📝 *Summary:*\n{summary}"
        )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")

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
    ]
