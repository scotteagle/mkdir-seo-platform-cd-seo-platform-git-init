import os
import httpx
from .base import Provider


class GeminiProvider(Provider):
    key = "gemini"

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_GENAI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    async def query(self, text: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                json={"contents": [{"parts": [{"text": text}]}]},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
