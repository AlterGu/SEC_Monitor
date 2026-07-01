import logging

from openai import AsyncOpenAI

import config

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        kwargs = {"api_key": config.OPENAI_API_KEY}
        if config.OPENAI_BASE_URL:
            kwargs["base_url"] = config.OPENAI_BASE_URL
        _client = AsyncOpenAI(**kwargs)
    return _client


SYSTEM_PROMPT = """You are a financial analyst assistant. Summarize SEC filing documents in a clear, structured outline format.

Rules:
- Output MUST be in Chinese (中文)
- Use numbered outline format with bullet points
- Focus on key items: financial results, material agreements, risk factors, business changes, acquisitions, executive changes
- Include specific numbers/percentages when available
- Keep it concise but comprehensive (aim for 5-15 bullet points)
- For 8-K: highlight which items are being reported (e.g., Item 2.02 Results of Operations)
- For 10-K/10-Q: focus on revenue, earnings, guidance, risk factor changes
- For S-1: focus on IPO details, use of proceeds, business model"""


async def summarize_filing(content: str, form_type: str, company_name: str) -> str:
    """Summarize a SEC filing using OpenAI."""
    if not content.strip():
        return "No content available to summarize."

    client = _get_client()

    user_prompt = f"""Please summarize this {form_type} filing from {company_name}:

{content}"""

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        full_summary = ""
        for attempt in range(3):  # max 3 calls = 6000 tokens
            response = await client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=messages,
                max_tokens=2000,
                temperature=0.3,
            )
            logger.debug(f"OpenAI response type: {type(response)}")

            if isinstance(response, str):
                logger.error(f"OpenAI returned string instead of object: {response[:200]}")
                return f"API error: {response[:200]}"

            if not hasattr(response, 'choices') or not response.choices:
                logger.error(f"Invalid response structure: {response}")
                return "API returned invalid response format"

            choice = response.choices[0]
            chunk = choice.message.content or ""
            full_summary += chunk

            if choice.finish_reason != "length":
                break

            # Truncated: ask model to continue
            logger.info(f"Summary truncated (attempt {attempt + 1}), continuing...")
            messages.append({"role": "assistant", "content": chunk})
            messages.append({"role": "user", "content": "请继续，从上次中断的地方接着写，不要重复已有内容。"})

        return full_summary.strip() or "Summary unavailable."
    except Exception as e:
        logger.error(f"OpenAI summarization failed: {e}", exc_info=True)
        return f"Summary generation failed: {str(e)[:100]}"
