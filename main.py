import logging
import sys

from telegram.ext import ApplicationBuilder

import config
from bot.handlers import get_handlers
from bot.scheduler import startup_sync
from db.database import init_db, close_db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Check your .env file.")
        sys.exit(1)
    if not config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Check your .env file.")
        sys.exit(1)

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    for handler in get_handlers():
        app.add_handler(handler)

    async def on_startup(app):
        await init_db()
        await startup_sync(app)
        logger.info("SEC Monitor Bot started")

    async def on_shutdown(app):
        await close_db()
        logger.info("SEC Monitor Bot stopped")

    app.post_init = on_startup
    app.post_shutdown = on_shutdown

    logger.info("Starting SEC Monitor Bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
