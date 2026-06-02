# SEC Monitor Telegram Bot

[English](README.md) | 中文

一个 Telegram 机器人，自动监控 SEC EDGAR 上指定股票的文件更新，并通过 AI 生成结构化摘要推送到 Telegram。

## 功能特性

- **股票监控**: 输入股票代码即可开始监控（如 `/monitor AAPL`）
- **自动轮询**: 定时检查 SEC EDGAR 新文件（默认 60 分钟，可自定义）
- **AI 摘要**: 使用 OpenAI 兼容 API 生成结构化大纲摘要
- **多种文件类型**: 监控 10-K、10-Q、8-K、S-1、20-F、6-K 等
- **即时检查**: 手动触发 `/check <TICKER>` 立即获取最新文件
- **多用户支持**: 每个用户独立的订阅和设置
- **持久化存储**: SQLite 数据库，重启不丢失
- **Docker 部署**: 一条命令即可运行

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/AlterGu/SEC_Monitor.git
cd SEC_Monitor
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的凭证：

```env
# Telegram Bot Token（从 @BotFather 获取）
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here

# OpenAI 兼容 API Key
OPENAI_API_KEY=your-openai-api-key-here

# API Base URL（留空使用 OpenAI 官方地址，第三方平台填对应地址）
OPENAI_BASE_URL=

# 模型 ID
OPENAI_MODEL=gpt-4o-mini

# 检查间隔（分钟），默认 60
DEFAULT_INTERVAL_MINUTES=60

# SEC EDGAR 要求的 User-Agent（必须包含联系方式，否则会被封禁）
USER_AGENT=SEC Monitor Bot (your-email@example.com)

# SQLite 数据库路径
DB_PATH=data/sec_monitor.db
```

### 3. Docker 运行（推荐）

**方式 A: 使用 GitHub Container Registry 预构建镜像（最简单）**

无需克隆仓库，只需创建 `.env` 文件后直接运行：

```bash
docker pull ghcr.io/altergu/sec_monitor:main
docker run -d --name sec-monitor --env-file .env -v sec-data:/app/data ghcr.io/altergu/sec_monitor:main
```

**方式 B: 从源码构建**

```bash
docker-compose up -d
```

### 4. 本地运行

```bash
pip install -r requirements.txt
python main.py
```

## 机器人命令

| 命令 | 说明 |
|------|------|
| `/start` | 显示欢迎信息和命令列表 |
| `/monitor <TICKER>` | 开始监控某只股票（立即检查一次） |
| `/unmonitor <TICKER>` | 停止监控 |
| `/list` | 查看当前监控的所有股票 |
| `/check <TICKER>` | 立即检查是否有新文件 |
| `/interval <MINUTES>` | 设置检查间隔（5-1440 分钟） |

### 使用示例

```
/monitor RKLB
```

机器人回复：
```
✅ Now monitoring Rocket Lab USA Inc (RKLB)
Checking every 60 minutes.
Use /check RKLB to check now.
📬 Found 3 new filing(s) for RKLB...
```

随后推送通知：
```
🔔 SEC Filing Alert: RKLB

📋 Form: 8-K
🏢 Company: Rocket Lab USA Inc
📅 Filed: 2024-03-15
🔗 Filing: View on SEC
📄 Document: Read Full

📝 Summary:
1. Item 1.01 - Entry into Material Agreement
   - 与某政府机构签署了价值 $500M 的合同...
2. Item 2.02 - Results of Operations
   - Q1 收入同比增长 35%，达 $120M...
3. Item 9.01 - Financial Statements
   - 附上财务报表...
```

## 配置说明

### 使用第三方 OpenAI 兼容 API

支持任何兼容 OpenAI 接口的第三方平台。只需修改 `OPENAI_BASE_URL`：

```env
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=Qwen/Qwen2.5-72B-Instruct
```

### 环境变量一览

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `TELEGRAM_BOT_TOKEN` | 是 | - | Telegram Bot Token，从 @BotFather 获取 |
| `OPENAI_API_KEY` | 是 | - | OpenAI 或第三方平台的 API Key |
| `OPENAI_BASE_URL` | 否 | （空） | 第三方 API 地址，留空使用 OpenAI 官方 |
| `OPENAI_MODEL` | 否 | `gpt-4o-mini` | 用于摘要的模型 ID |
| `DEFAULT_INTERVAL_MINUTES` | 否 | `60` | 默认轮询间隔（分钟） |
| `USER_AGENT` | 否 | `SEC Monitor Bot (...)` | SEC 请求的 User-Agent（必须包含联系方式） |
| `DB_PATH` | 否 | `data/sec_monitor.db` | SQLite 数据库文件路径 |
| `DB_BACKEND` | 否 | `sqlite` | 数据库后端：`sqlite` 或 `supabase` |
| `SUPABASE_URL` | 否 | - | Supabase 项目 URL（`DB_BACKEND=supabase` 时必填） |
| `SUPABASE_KEY` | 否 | - | Supabase anon key（`DB_BACKEND=supabase` 时必填） |

### 使用 Supabase（可选）

设置 `DB_BACKEND=supabase` 并填入 Supabase 凭证。然后在 Supabase SQL Editor 中创建所需表：

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

## 项目结构

```
SEC_Monitor/
├── main.py                      # 程序入口
├── config.py                    # 环境变量与配置
├── requirements.txt             # Python 依赖
├── Dockerfile                   # Docker 镜像定义
├── docker-compose.yml           # Docker Compose 配置
├── .env.example                 # 环境变量模板
├── bot/
│   ├── handlers.py              # Telegram 命令处理器
│   └── scheduler.py             # 定时轮询调度
├── sec/
│   └── edgar.py                 # SEC EDGAR API 客户端
├── summarizer/
│   └── openai_summarizer.py     # OpenAI 摘要生成
└── db/
    └── database.py              # SQLite 数据库操作
```

## 架构图

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Telegram API │◄───►│  Bot Server  │◄───►│  SEC EDGAR  │
│              │     │  (异步)       │     │  REST API   │
└─────────────┘     │              │     └─────────────┘
                     │  ┌────────┐  │
                     │  │ OpenAI │  │
                     │  │ 摘要   │  │
                     │  └────────┘  │
                     │  ┌────────┐  │
                     │  │SQLite  │  │
                     │  └────────┘  │
                     └──────────────┘
```

## 技术栈

- **Python 3.11+**
- **python-telegram-bot** - Telegram Bot API（异步）
- **OpenAI SDK** - LLM 摘要生成
- **APScheduler** - 定时任务调度（通过 python-telegram-bot 内置 job queue）
- **aiohttp** - 异步 HTTP 客户端
- **aiosqlite** - 异步 SQLite 数据库
- **BeautifulSoup4** - SEC 文件 HTML 解析

## 注意事项

- SEC EDGAR 要求所有请求必须包含带联系方式的 `User-Agent` header，否则请求会被拒绝
- 使用 python-telegram-bot 内置的 job queue（底层封装 APScheduler）进行调度
- 文件内容超过 15,000 字符时会截断后再送入模型摘要
- 首次 `/monitor` 时会立即检查近期文件并发送摘要

## 许可证

MIT
