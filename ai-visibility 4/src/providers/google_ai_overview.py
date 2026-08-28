import os
import httpx
from .base import Provider


class GoogleAIOverviewProvider(Provider):
    """
    Google has no public API for AI Overviews, so this goes through a
    third-party SERP API (SerpApi, ValueSerp, etc.) that captures the
    'ai_overview' block from the live results page. Swap SERP_API_URL /
    the response-parsing key if you use a different provider.
    """

    key = "google_ai_overview"

    def __init__(self):
        self.api_key = os.getenv("SERP_API_KEY")
        self.base_url = os.getenv("SERP_API_URL", "https://serpapi.com/search")

    async def query(self, text: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                self.base_url,
                params={"q": text, "api_key": self.api_key, "engine": "google"},
            )
            resp.raise_for_status()
            data = resp.json()
            overview = data.get("ai_overview", {})
            # Different SERP providers shape this differently; fall back to
            # stringifying whatever we got so the detector still has content.
            return overview.get("text") if isinstance(overview, dict) else str(overview)
