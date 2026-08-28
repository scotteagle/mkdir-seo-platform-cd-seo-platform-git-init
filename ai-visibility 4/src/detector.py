import os
import json
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DETECTOR_PROMPT = """You are analyzing a response from an AI answer engine to determine
whether a specific brand was mentioned, and how.

Brand name: {brand_name}
Known aliases: {aliases}

Response text to analyze:
---
{response_text}
---

Return ONLY a JSON object, no preamble or markdown fences, with this exact shape:
{{
  "mentioned": true or false,
  "prominence": a number from 0.0 to 1.0 (1.0 = the headline/top recommendation,
    0.5 = mentioned alongside several alternatives, 0.1 = mentioned only in passing),
  "sentiment": "positive" | "neutral" | "negative",
  "snippet": "a short (<200 char) excerpt or paraphrase showing the mention, or empty string if not mentioned"
}}"""


def analyze_mention(brand_name: str, aliases: list[str], response_text: str) -> dict:
    if not response_text:
        return {"mentioned": False, "prominence": 0.0, "sentiment": "neutral", "snippet": ""}

    prompt = DETECTOR_PROMPT.format(
        brand_name=brand_name,
        aliases=", ".join(aliases) if aliases else "(none)",
        response_text=response_text[:6000],  # keep the analysis call cheap
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Model didn't return clean JSON; fail safe rather than crash the job
        return {"mentioned": False, "prominence": 0.0, "sentiment": "neutral", "snippet": ""}
