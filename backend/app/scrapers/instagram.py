import httpx
from datetime import datetime
from typing import Optional
from app.scrapers.base import BaseScraper, RawPost
from app.config import settings


class InstagramScraper(BaseScraper):
    """
    Scrapes Instagram via Apify's Instagram Reel Scraper actor.
    Handles Reels and posts. Resistant to platform changes since Apify
    maintains the actor — update the actor ID if they release a new version.
    """

    # Apify actor for Instagram — update if Apify releases a newer version
    ACTOR_ID = "apify/instagram-reel-scraper"
    APIFY_BASE = "https://api.apify.com/v2"

    async def fetch_recent_posts(self, handle: str, since: Optional[datetime] = None) -> list[RawPost]:
        if not settings.apify_api_token:
            raise RuntimeError("APIFY_API_TOKEN not configured")

        async with httpx.AsyncClient(timeout=60) as client:
            # Start Apify actor run
            run_resp = await client.post(
                f"{self.APIFY_BASE}/acts/{self.ACTOR_ID}/runs",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                json={
                    "username": handle.lstrip("@"),
                    "resultsLimit": 20,
                },
            )
            run_resp.raise_for_status()
            run_id = run_resp.json()["data"]["id"]

            # Wait for run to finish (poll)
            import asyncio
            for _ in range(30):  # Max 5 min wait
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

            # Fetch results
            items_resp = await client.get(
                f"{self.APIFY_BASE}/acts/{self.ACTOR_ID}/runs/{run_id}/dataset/items",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            )
            items_resp.raise_for_status()
            items = items_resp.json()

        posts = []
        for item in items:
            posted_at = None
            if ts := item.get("timestamp"):
                posted_at = datetime.fromisoformat(ts)

            if since and posted_at and posted_at < since:
                continue

            posts.append(RawPost(
                platform="instagram",
                post_type="reel" if item.get("type") == "Video" else "post",
                post_url=item.get("url", ""),
                posted_at=posted_at,
                caption=item.get("caption"),
                video_url=item.get("videoUrl"),
                raw=item,
            ))

        return posts
