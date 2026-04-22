"""
Twitter/X adapter that ingests tweets via Gmail notification emails.

Flow:
  1. Poll Gmail API for messages from notify@x.com (or info@x.com)
  2. Parse the email HTML to recover tweet text, URL, handle, media
  3. Emit RawPost objects for the existing extraction pipeline

The HTML parser is the fragile bit. It is intentionally defensive
(multiple fallback strategies) and the parsing functions are pure so
they can be exercised against saved .eml fixtures without hitting
the Gmail API. See scripts/test_gmail_parse.py.
"""
from __future__ import annotations

import asyncio
import base64
import re
from datetime import datetime, timezone
from email import message_from_bytes
from email.message import Message
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, NotificationMetadata
from app.scrapers.base import RawPost

log = structlog.get_logger()

TWITTER_NOTIFICATION_SENDERS = ("notify@x.com", "info@x.com", "notify@twitter.com")
TWEET_URL_RE = re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+")
HANDLE_RE = re.compile(r"@(\w{1,15})")


class TwitterGmailAdapter(BaseAdapter):
    """Reads Twitter post-notification emails out of a Gmail inbox."""

    def __init__(self, credentials, label_id: Optional[str] = None):
        # Lazy import so the rest of the codebase doesn't pay the import cost
        # when Gmail ingestion isn't enabled.
        from googleapiclient.discovery import build

        self.service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        self.label_id = label_id

    async def fetch_new_posts(
        self, since: datetime
    ) -> list[tuple[RawPost, NotificationMetadata]]:
        # Gmail's `after:` operator only supports day granularity, so we
        # over-fetch and rely on internalDate filtering + DB dedup.
        return await asyncio.to_thread(self._fetch_sync, since)

    # -- Sync internals ----------------------------------------------------

    def _fetch_sync(self, since: datetime) -> list[tuple[RawPost, NotificationMetadata]]:
        since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
        from_clause = " OR ".join(f"from:{addr}" for addr in TWITTER_NOTIFICATION_SENDERS)
        query = f"({from_clause}) after:{since_utc.strftime('%Y/%m/%d')}"
        if self.label_id:
            query += f" label:{self.label_id}"

        listing = self.service.users().messages().list(
            userId="me", q=query, maxResults=50
        ).execute()

        message_refs = listing.get("messages", []) or []
        results: list[tuple[RawPost, NotificationMetadata]] = []

        for ref in message_refs:
            try:
                msg = self.service.users().messages().get(
                    userId="me", id=ref["id"], format="full"
                ).execute()
            except Exception as e:
                log.warning("gmail_fetch_failed", message_id=ref.get("id"), error=str(e))
                continue

            internal_ts = int(msg.get("internalDate", "0")) / 1000
            received_at = datetime.fromtimestamp(internal_ts, tz=timezone.utc)
            if received_at < since_utc:
                continue

            parsed = parse_gmail_message(msg)
            if parsed is not None:
                results.append(parsed)

        return results


# -- Pure parsing functions (no Gmail API dependency) ---------------------

def parse_gmail_message(msg: dict) -> Optional[tuple[RawPost, NotificationMetadata]]:
    """Parse a Gmail API message dict into a (RawPost, NotificationMetadata) pair."""
    msg_id = msg["id"]
    internal_ts = int(msg.get("internalDate", "0")) / 1000
    received_at = datetime.fromtimestamp(internal_ts, tz=timezone.utc)

    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    subject = headers.get("subject", "")
    sender = headers.get("from", "")

    html_body = _get_html_body(msg["payload"])
    if not html_body:
        log.info("gmail_no_html_body", message_id=msg_id)
        return None

    return parse_twitter_notification_html(
        html=html_body,
        subject=subject,
        sender=sender,
        received_at=received_at,
        notification_id=msg_id,
    )


def parse_twitter_notification_html(
    *,
    html: str,
    subject: str,
    sender: str,
    received_at: datetime,
    notification_id: str,
) -> Optional[tuple[RawPost, NotificationMetadata]]:
    """Pure parser — same code path the live adapter uses."""
    soup = BeautifulSoup(html, "html.parser")

    handle = _extract_handle(subject, soup)
    tweet_url = _extract_tweet_url(soup)
    tweet_text = _extract_tweet_text(soup, subject)
    media_urls = _extract_media_urls(soup)

    if not tweet_text and not tweet_url:
        log.warning(
            "twitter_email_unparseable",
            notification_id=notification_id,
            subject=subject,
        )
        return None

    raw_post = RawPost(
        platform="twitter",
        post_type="tweet",
        post_url=tweet_url or f"gmail://{notification_id}",
        posted_at=received_at,
        caption=tweet_text,
        description=subject or None,
        subtitles=None,
        video_url=None,
        raw={
            "gmail_message_id": notification_id,
            "creator_handle": handle,
            "media_urls": media_urls,
            "sender": sender,
            "source": "gmail_notification",
        },
    )
    metadata = NotificationMetadata(
        notification_id=notification_id,
        received_at=received_at,
        source_platform="gmail",
        raw_notification=html[:5000],
    )
    return raw_post, metadata


def parse_eml_bytes(data: bytes) -> Optional[tuple[RawPost, NotificationMetadata]]:
    """Parse a downloaded .eml file (for use by scripts/test_gmail_parse.py)."""
    msg: Message = message_from_bytes(data)
    subject = msg.get("Subject", "")
    sender = msg.get("From", "")
    received_at = datetime.now(timezone.utc)
    html = _html_from_eml(msg)
    if html is None:
        return None
    notification_id = msg.get("Message-ID", "eml-fixture").strip("<>")
    return parse_twitter_notification_html(
        html=html,
        subject=subject,
        sender=sender,
        received_at=received_at,
        notification_id=notification_id,
    )


# -- Low-level helpers ----------------------------------------------------

def _get_html_body(payload: dict) -> Optional[str]:
    """Recursively walk a Gmail payload tree and return the first text/html body."""
    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []) or []:
        body = _get_html_body(part)
        if body:
            return body
    return None


def _html_from_eml(msg: Message) -> Optional[str]:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return None
    if msg.get_content_type() == "text/html":
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return None


def _extract_handle(subject: str, soup: BeautifulSoup) -> Optional[str]:
    # Subject typically: "Display Name (@handle): tweet preview"
    m = HANDLE_RE.search(subject)
    if m:
        return m.group(1)
    # Fallback — first @handle anywhere in the body
    text = soup.get_text(" ", strip=True)
    m = HANDLE_RE.search(text)
    return m.group(1) if m else None


def _extract_tweet_url(soup: BeautifulSoup) -> Optional[str]:
    for a in soup.find_all("a", href=True):
        m = TWEET_URL_RE.search(a["href"])
        if m:
            return m.group(0)
    # Last-ditch: search raw HTML for a tweet URL
    m = TWEET_URL_RE.search(str(soup))
    return m.group(0) if m else None


def _extract_tweet_text(soup: BeautifulSoup, subject: str) -> Optional[str]:
    """Find the tweet body text.

    Strategy:
      1. Look for a long-text block (largest <td>/<div> with substantive text)
         that doesn't look like boilerplate (footer, unsubscribe, etc.)
      2. Fall back to the subject minus the "Name (@handle):" prefix.
    """
    boilerplate_markers = (
        "unsubscribe",
        "notification settings",
        "twitter, inc",
        "x corp",
        "this email was sent",
        "you received this",
    )

    candidates: list[str] = []
    for tag in soup.find_all(["td", "div", "p", "span"]):
        text = tag.get_text(" ", strip=True)
        if len(text) < 20:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in boilerplate_markers):
            continue
        candidates.append(text)

    if candidates:
        # Take the longest non-boilerplate text block.
        return max(candidates, key=len)

    # Fallback to subject body
    if subject:
        m = re.match(r"^.*?\(@\w+\)\s*[:\-]?\s*(.+)$", subject)
        if m:
            return m.group(1).strip() or None
    return None


def _extract_media_urls(soup: BeautifulSoup) -> list[str]:
    media: list[str] = []
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if "twimg.com" in src:
            media.append(src)
    return media
