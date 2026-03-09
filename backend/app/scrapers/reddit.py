import httpx
from datetime import datetime, timezone
from typing import Optional
from app.scrapers.base import BaseScraper, RawPost
from app.config import settings


class RedditScraper(BaseScraper):
    """
    Scrapes Reddit using the official public JSON API (no auth required for read-only).
    Used for crowd-sourced picks from betting subreddits.
    """

    BASE = "https://www.reddit.com"

    async def fetch_recent_posts(self, handle: str, since: Optional[datetime] = None) -> list[RawPost]:
        """
        handle: subreddit name (e.g. "sportsbook") or "u/username" for user posts
        """
        if handle.startswith("u/"):
            url = f"{self.BASE}/{handle}/submitted.json"
        else:
            subreddit = handle.lstrip("r/")
            url = f"{self.BASE}/r/{subreddit}/new.json"

        async with httpx.AsyncClient(
            headers={"User-Agent": settings.reddit_user_agent},
            timeout=30,
        ) as client:
            resp = await client.get(url, params={"limit": 50})
            resp.raise_for_status()
            data = resp.json()

        posts = []
        for child in data.get("data", {}).get("children", []):
            item = child.get("data", {})
            posted_at = datetime.fromtimestamp(item.get("created_utc", 0), tz=timezone.utc)

            if since and posted_at < since:
                continue

            posts.append(RawPost(
                platform="reddit",
                post_type="reddit_post",
                post_url=f"https://reddit.com{item.get('permalink', '')}",
                posted_at=posted_at,
                caption=item.get("title"),
                description=item.get("selftext"),
                raw=item,
            ))

        return posts

    async def fetch_comments(self, post_url: str) -> list[RawPost]:
        """Fetch comments from a specific Reddit post."""
        json_url = post_url.rstrip("/") + ".json"
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.reddit_user_agent},
            timeout=30,
        ) as client:
            resp = await client.get(json_url)
            resp.raise_for_status()
            data = resp.json()

        comments = []
        if len(data) > 1:
            for child in data[1].get("data", {}).get("children", []):
                item = child.get("data", {})
                if not item.get("body"):
                    continue
                posted_at = datetime.fromtimestamp(item.get("created_utc", 0), tz=timezone.utc)
                comments.append(RawPost(
                    platform="reddit",
                    post_type="reddit_comment",
                    post_url=post_url,
                    posted_at=posted_at,
                    caption=item.get("body"),
                    raw=item,
                ))
        return comments
