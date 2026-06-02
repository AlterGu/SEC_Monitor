# SEC Monitor Telegram Bot

English | [中文](README_CN.md)

A Telegram bot that monitors SEC EDGAR filings for specified stocks and sends AI-summarized notifications.

## Features

- **Stock Monitoring**: Add any US-listed stock by ticker symbol (e.g., `/monitor AAPL`)
- **Automatic Polling**: Periodically checks SEC EDGAR for new filings (default: every 60 minutes, customizable)
- **AI Summarization**: Uses OpenAI-compatible API to generate structured summaries of SEC filings
- **Multiple Filing Types**: Monitors 10-K, 10-Q, 8-K, S-1, 20-F, 6-K filings
- **Instant Check**: Manually trigger a check with `/check <TICKER>`
- **Multi-user Support**: Each user has independent subscriptions and settings
- **Persistent Storage**: SQLite database survives bot restarts
- **Docker Ready**: One-command deployment with Docker Compose

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/AlterGu/SEC_Monitor.git
cd SEC_Monitor
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here

# OpenAI-compatible API Key
OPENAI_API_KEY=your-openai-api-key-here

# Base URL (leave empty for OpenAI official, or set for third-party providers)
OPENAI_BASE_URL=

# Model ID
OPENAI_MODEL=gpt-4o-mini

# Check interval in minutes (default: 60)
DEFAULT_INTERVAL_MINUTES=60

# SEC EDGAR requires a User-Agent with contact info
USER_AGENT=SEC Monitor Bot (your-email@example.com)

# SQLite database path
DB_PATH=data/sec_monitor.db
```

### 3. Run with Docker (Recommended)

**Option A: Use pre-built image from GitHub Container Registry (easiest)**

No need to clone the repo. Just create a `.env` file and run:

```bash
docker pull ghcr.io/altergu/sec_monitor:main
docker run -d --name sec-monitor --env-file .env -v sec-data:/app/data ghcr.io/altergu/sec_monitor:main
```

**Option B: Build from source**

```bash
docker-compose up -d
```

### 4. Run Locally

```bash
pip install -r requirements.txt
python main.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and command list |
| `/monitor <TICKER>` | Start monitoring a stock (checks immediately) |
| `/unmonitor <TICKER>` | Stop monitoring a stock |
| `/list` | Show all monitored stocks |
| `/check <TICKER>` | Manually check for new filings now |
| `/interval <MINUTES>` | Set check interval (5-1440 minutes) |

### Example Usage

```
/monitor RKLB
```

Bot responds:
```
✅ Now monitoring Rocket Lab USA Inc (RKLB)
Checking every 60 minutes.
Use /check RKLB to check now.
📬 Found 3 new filing(s) for RKLB...
```

Then sends notifications:
```
🔔 SEC Filing Alert: RKLB

📋 Form: 8-K
🏢 Company: Rocket Lab USA Inc
📅 Filed: 2024-03-15
🔗 Filing: View on SEC
📄 Document: Read Full

📝 Summary:
1. Item 1.01 - Entry into Material Agreement
   - Signed a $500M contract with a government agency...
2. Item 2.02 - Results of Operations
   - Q1 revenue increased 35% YoY to $120M...
3. Item 9.01 - Financial Statements
   - Financial statements attached...
```

## Configuration

### Third-Party OpenAI Providers

The bot supports any OpenAI-compatible API. Set `OPENAI_BASE_URL` to your provider's endpoint:

```env
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=Qwen/Qwen2.5-72B-Instruct
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot token from @BotFather |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key or third-party key |
| `OPENAI_BASE_URL` | No | (empty) | Custom API base URL for third-party providers |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model ID to use for summarization |
| `DEFAULT_INTERVAL_MINUTES` | No | `60` | Default polling interval in minutes |
| `USER_AGENT` | No | `SEC Monitor Bot (...)` | User-Agent header for SEC requests (must include contact info) |
| `DB_PATH` | No | `data/sec_monitor.db` | SQLite database file path |
| `DB_BACKEND` | No | `sqlite` | Database backend: `sqlite` or `supabase` |
| `SUPABASE_URL` | No | - | Supabase project URL (required if `DB_BACKEND=supabase`) |
| `SUPABASE_KEY` | No | - | Supabase **service_role** key (required if `DB_BACKEND=supabase`) |

### Using Supabase (Optional)

Set `DB_BACKEND=supabase` and provide your Supabase credentials. Use the **service_role** key (found in Supabase Dashboard > Project Settings > API), not the anon key. The service_role key bypasses Row Level Security, which is required for this server-side application.

Then create the required tables in Supabase SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    ticker TEXT NOT NULL,
    cik TEXT NOT NULL,
    company_name TEXT NOT NULL DEFAULT '',
    interval_minutes INT NOT NULL DEFAULT 60,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS seen_filings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    accession_no TEXT NOT NULL,
    ticker TEXT NOT NULL DEFAULT '',
    seen_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, accession_no)
);

CREATE INDEX IF NOT EXISTS idx_seen_user_acc ON seen_filings(user_id, accession_no);
CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id);
```

## Project Structure

```
SEC_Monitor/
├── main.py                      # Entry point
├── config.py                    # Environment variables & settings
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose config
├── .env.example                 # Environment template
├── bot/
│   ├── handlers.py              # Telegram command handlers
│   └── scheduler.py             # APScheduler polling logic
├── sec/
│   └── edgar.py                 # SEC EDGAR API client
├── summarizer/
│   └── openai_summarizer.py     # OpenAI summarization
└── db/
    └── database.py              # SQLite operations
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Telegram API │◄───►│  Bot Server  │◄───►│  SEC EDGAR  │
│              │     │  (async)     │     │  REST API   │
└─────────────┘     │              │     └─────────────┘
                     │  ┌────────┐  │
                     │  │ OpenAI │  │
                     │  │Summary │  │
                     │  └────────┘  │
                     │  ┌────────┐  │
                     │  │SQLite  │  │
                     │  └────────┘  │
                     └──────────────┘
```

## Tech Stack

- **Python 3.11+**
- **python-telegram-bot** - Telegram Bot API (async)
- **OpenAI SDK** - LLM-powered summarization
- **APScheduler** - Periodic job scheduling (via python-telegram-bot job queue)
- **aiohttp** - Async HTTP client for SEC EDGAR
- **aiosqlite** - Async SQLite database
- **BeautifulSoup4** - HTML parsing for SEC filings

## Notes

- SEC EDGAR requires all requests to include a `User-Agent` header with contact information. Requests without it will be blocked.
- The bot uses python-telegram-bot's built-in job queue (wraps APScheduler) for scheduling, not a standalone scheduler.
- Filing content is truncated to 15,000 characters before summarization to stay within model token limits.
- On first `/monitor`, the bot immediately checks for recent filings and sends summaries.

## License

MIT
