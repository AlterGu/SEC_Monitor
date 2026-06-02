import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # 留空则使用官方地址, 第三方填如 https://api.example.com/v1
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_INTERVAL_MINUTES = int(os.getenv("DEFAULT_INTERVAL_MINUTES", "60"))
USER_AGENT = os.getenv("USER_AGENT", "SEC Monitor Bot (your-email@example.com)")
DB_PATH = os.getenv("DB_PATH", "data/sec_monitor.db")
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite")  # sqlite or supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
# Direct PostgreSQL connection string for DDL operations (auto-create tables)
# Get from Supabase Dashboard > Settings > Database > Connection string > URI
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")

# Access control
# Comma-separated Telegram user IDs. If set, only these users can access the bot.
ALLOWED_USER_IDS: list[int] = [
    int(uid.strip()) for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") if uid.strip()
]
# Access password. If ALLOWED_USER_IDS is empty and this is set, users must enter this password first.
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")

# SEC filing types to monitor by default
DEFAULT_FORM_TYPES = ["10-K", "10-Q", "8-K", "S-1", "20-F", "6-K"]

MAX_SUMMARY_CHARS = 15000  # Max chars to send to OpenAI for summarization
