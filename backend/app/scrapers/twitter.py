"""
Twitter/X scraper via Apify.

Note: Twitter's official API is expensive for this use case.
Using Apify's Twitter scraper actor instead — handles auth + anti-bot measures.
"""
import httpx
import asyncio
from datetime import datetime
from typing import Optional
from app.scrapers.base import BaseScraper, RawPost
from app.config import settings


class TwitterScraper(BaseScraper):
    ACTOR_ID = "apify/twitter-scraper"
    APIFY_BASE = "https://api.apify.com/v2"

    async def fetch_recent_posts(self, handle: str, since: Optional[datetime] = None) -> list[RawPost]:
        if not settings.apify_api_token:
            raise RuntimeError("APIFY_API_TOKEN not configured")

        async with httpx.AsyncClient(timeout=120) as client:
            run_resp = await client.post(
                f"{self.APIFY_BASE}/acts/{self.ACTOR_ID}/runs",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                json={
                    "startUrls": [{"url": f"https://twitter.com/{handle.lstrip('@')}"}],
                    "maxItems": 30,
                    "addUserInfo": False,
                },
            )
            run_resp.raise_for_status()
            run_id = run_resp.json()["data"]["id"]

            for _ in range(30):
                await asyncio.sleep(10)
                status_resp = await client.get(
                    f"{self.APIFY_BASE}/acts/{self.ACTOR_ID}/runs/{run_id}",
                    headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                )
                status = status_resp.json()["data"]["status"]
                if status == "SUCCEEDED":
                    break
                if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    raise RuntimeError(f"Apify run {status}")

            items_resp = await client.get(
                f"{self.APIFY_BASE}/acts/{self.ACTOR_ID}/runs/{run_id}/dataset/items",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            )
            items_resp.raise_for_status()
            items = items_resp.json()

        posts = []
        for item in items:
            posted_at = None
            if ts := item.get("createdAt"):
                posted_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))

            if since and posted_at and posted_at < since:
                continue

            posts.append(RawPost(
                platform="twitter",
                post_type="tweet",
                post_url=item.get("url", ""),
                posted_at=posted_at,
                caption=item.get("text"),
                raw=item,
            ))

        return posts
