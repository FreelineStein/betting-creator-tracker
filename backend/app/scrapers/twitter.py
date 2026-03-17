"""
Twitter/X scraper via oEmbed API.

Uses Twitter's free, unauthenticated oEmbed endpoint to fetch tweet text
from specific URLs. No API keys required.

Limitation: cannot fetch a user's full timeline — requires tweet URLs to be
submitted directly. Upgrade to the official Twitter API for automated
timeline scraping once the product is validated.
"""
import re
import httpx
import structlog
from datetime import datetime
from html import unescape
from typing import Optional
from app.scrapers.base import BaseScraper, RawPost

log = structlog.get_logger()

OEMBED_URL = "https://publish.twitter.com/oembed"


class TwitterScraper(BaseScraper):
    """
    Fetches tweet text via Twitter's oEmbed API.

    Use fetch_tweets() with specific tweet URLs. fetch_recent_posts()
    is not supported since oEmbed cannot scrape timelines.
    """

    async def fetch_recent_posts(self, handle: str, since: Optional[datetime] = None) -> list[RawPost]:
        raise NotImplementedError(
            "Twitter oEmbed does not support timeline scraping. "
            "Use fetch_tweets() with specific tweet URLs instead."
        )

    async def fetch_tweets(self, urls: list[str]) -> list[RawPost]:
        """Fetch tweet text for a list of tweet URLs via oEmbed."""
        posts = []
        async with httpx.AsyncClient(timeout=30) as client:
            for url in urls:
                try:
                    post = await self._fetch_single(client, url)
                    if post:
                        posts.append(post)
                except Exception as e:
                    log.error("Failed to fetch tweet", url=url, error=str(e))
        return posts

    async def _fetch_single(self, client: httpx.AsyncClient, tweet_url: str) -> Optional[RawPost]:
        """Fetch a single tweet via oEmbed and parse into RawPost."""
        normalized_url = tweet_url.replace("https://x.com/", "https://twitter.com/")

        resp = await client.get(OEMBED_URL, params={"url": normalized_url, "omit_script": "true"})
        if resp.status_code == 404:
            log.warning("Tweet not found", url=tweet_url)
            return None
        resp.raise_for_status()

        data = resp.json()
        text = _extract_text_from_html(data.get("html", ""))
        if not text:
            log.warning("No text extracted from oEmbed", url=tweet_url)
            return None

        posted_at = _extract_date_from_html(data.get("html", ""))
        author_handle = _extract_handle_from_url(data.get("author_url", ""))

        log.info("Tweet fetched", url=tweet_url, author=author_handle, text_len=len(text))

        return RawPost(
            platform="twitter",
            post_type="tweet",
            post_url=data.get("url", tweet_url),
            posted_at=posted_at,
            caption=text,
            raw={
                "author_name": data.get("author_name"),
                "author_handle": author_handle,
                "author_url": data.get("author_url"),
                "source": "oembed",
            },
        )


def _extract_text_from_html(html: str) -> Optional[str]:
    """Extract tweet text from oEmbed HTML blockquote."""
    match = re.search(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
    if not match:
        return None
    text = match.group(1)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return text.strip()


def _extract_date_from_html(html: str) -> Optional[datetime]:
    """Extract the tweet date from the oEmbed HTML link text."""
    match = re.search(r'href="[^"]*twitter\.com/[^"]*">([^<]+)</a>\s*</blockquote>', html)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1).strip(), "%B %d, %Y")
    except (ValueError, TypeError):
        return None


def _extract_handle_from_url(author_url: str) -> Optional[str]:
    """Extract @handle from author URL like https://twitter.com/gavinmchughh."""
    if not author_url:
        return None
    match = re.search(r"twitter\.com/(\w+)", author_url)
    return f"@{match.group(1)}" if match else None
