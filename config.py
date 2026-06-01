import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_INTERVAL_MINUTES = int(os.getenv("DEFAULT_INTERVAL_MINUTES", "60"))
USER_AGENT = os.getenv("USER_AGENT", "SEC Monitor Bot (your-email@example.com)")
DB_PATH = os.getenv("DB_PATH", "data/sec_monitor.db")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# SEC filing types to monitor by default
DEFAULT_FORM_TYPES = ["10-K", "10-Q", "8-K", "S-1", "20-F", "6-K"]

MAX_SUMMARY_CHARS = 15000  # Max chars to send to OpenAI for summarization
