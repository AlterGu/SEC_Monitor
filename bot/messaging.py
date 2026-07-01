import logging
import re

from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000

# MarkdownV2 special characters that must be escaped
_V2_SPECIAL = set("_*[]()~`>#+-=|{}.!")


def _escape_chars(text: str) -> str:
    """Escape all MarkdownV2 special characters in text."""
    result = []
    for c in text:
        if c in _V2_SPECIAL:
            result.append("\\")
        result.append(c)
    return "".join(result)


def escape_markdown_v2(text: str) -> str:
    """Escape text for Telegram MarkdownV2, preserving **bold** formatting."""
    result = []
    for part in re.split(r"(\*\*.+?\*\*)", text):
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            # Bold segment: escape inner content but keep ** delimiters
            result.append("**" + _escape_chars(part[2:-2]) + "**")
        else:
            result.append(_escape_chars(part))
    return "".join(result)


def split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    """Split a long message into chunks at newline boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1 or split_at < max_len // 2:
            split_at = max_len

        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()

    return chunks


async def send_long_message(bot, chat_id: int, text: str, parse_mode: str = ParseMode.MARKDOWN_V2):
    """Send a message, splitting into multiple parts if it exceeds Telegram's limit."""
    chunks = split_message(text)

    for i, chunk in enumerate(chunks):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Failed to send chunk {i + 1}/{len(chunks)} to {chat_id}: {e}")
            # Fallback: plain text without markup
            try:
                await bot.send_message(chat_id=chat_id, text=chunk, disable_web_page_preview=True)
            except Exception as e2:
                logger.error(f"Fallback send also failed: {e2}")
