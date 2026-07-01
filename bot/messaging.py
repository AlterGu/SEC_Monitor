import logging

from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# Telegram limit is 4096; leave margin for safety
MAX_MSG_LEN = 4000


def split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    """Split a long message into chunks at newline boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        # Try to split at the last newline within the limit
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1 or split_at < max_len // 2:
            split_at = max_len  # no good newline, hard split

        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()

    return chunks


async def send_long_message(bot, chat_id: int, text: str, parse_mode: str = ParseMode.HTML):
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
