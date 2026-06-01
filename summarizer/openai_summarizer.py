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
- Output in the SAME LANGUAGE as the filing (usually English)
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
        response = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
        )
        return response.choices[0].message.content or "Summary unavailable."
    except Exception as e:
        logger.error(f"OpenAI summarization failed: {e}")
        return f"Summary generation failed: {e}"
