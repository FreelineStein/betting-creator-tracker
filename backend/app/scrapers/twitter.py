"""
Twitter/X scraper via oEmbed API.

Uses Twitter's free, unauthenticated oEmbed endpoint to fetch tweet text
from specific URLs. No API keys required.

Limitation: cannot fetch a user's full timeline — requires tweet URLs to be
submitted directly. Upgrade to the official Twitter API for automated
timeline scraping once the product is validated.
"""
import asyncio
import re
import httpx
import structlog
from datetime import datetime
from html import unescape
from typing import Optional
from app.scrapers.base import BaseScraper, RawPost

log = structlog.get_logger()

OEMBED_URL = "https://publish.twitter.com/oembed"

# Cap concurrent oEmbed calls so a burst of anonymous /submissions traffic
# can't blow through X's free quota in seconds. Process-local — fine for the
# single-worker Railway deploy; revisit if we scale horizontally.
_OEMBED_SEMAPHORE = asyncio.Semaphore(4)


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

        async with _OEMBED_SEMAPHORE:
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


async def extract_image_url(tweet_url: str) -> Optional[str]:
    """
    Extract the image URL from a tweet using fxtwitter.com (open-source Twitter embed proxy).
    Falls back to direct x.com/twitter.com if fxtwitter fails.
    Returns the image URL or None if no image found.
    """
    # Extract the path from the tweet URL
    path_match = re.search(r"(?:twitter\.com|x\.com)(/\w+/status/\d+)", tweet_url)
    if not path_match:
        return None

    path = path_match.group(1)
    sources = [
        f"https://fxtwitter.com{path}",
        f"https://vxtwitter.com{path}",
    ]

    for source_url in sources:
        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"},
            ) as client:
                resp = await client.get(source_url)
                if resp.status_code != 200:
                    continue
                html = resp.text

            # Try og:image first, then twitter:image
            for pattern in [
                r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
                r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
                r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
                r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']twitter:image["\']',
            ]:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    image_url = unescape(match.group(1))
                    # Filter out profile images and default cards
                    if "profile_images" in image_url or "card_img" in image_url:
                        continue
                    log.info("Extracted image URL from tweet", url=tweet_url, image_url=image_url[:120])
                    return image_url

        except Exception as e:
            log.warning("Image extraction source failed", source=source_url, error=str(e))
            continue

    log.info("No image found in tweet", url=tweet_url)
    return None


async def extract_text_from_image(image_url: str) -> Optional[str]:
    """
    Use Claude vision to extract text from a tweet image.
    Designed for betting pick screenshots, bet slips, etc.
    """
    from app.config import settings

    if not settings.anthropic_api_key:
        log.warning("No Anthropic API key — cannot extract text from image")
        return None

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        message = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "url",
                            "url": image_url,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract ALL text from this image exactly as written. "
                            "This is likely a sports betting pick or bet slip. "
                            "Include team names, spreads, lines, odds, player names, "
                            "prop bets, and any other betting-related information. "
                            "Return ONLY the extracted text, nothing else."
                        ),
                    },
                ],
            }],
        )

        extracted = message.content[0].text.strip()
        if extracted:
            log.info("Extracted text from image", text_len=len(extracted))
        return extracted if extracted else None

    except Exception as e:
        log.error("Image text extraction failed", error=str(e))
        return None
