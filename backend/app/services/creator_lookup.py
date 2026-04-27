"""
Creator lookup and auto-creation by Twitter handle.

Used by the anonymous /submissions endpoint: when a user submits a tweet URL
from a creator we don't already track, we auto-create a Creator record using
the author metadata returned by Twitter's oEmbed endpoint.

Auto-created creators get tracking_active=False so they don't appear on the
public list (or get scheduled for scraping) until an admin reviews them.
This is the "soft gate" that protects W/L records from drive-by additions.
"""
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.models import Creator, CreatorTier

log = structlog.get_logger()


def normalize_handle(handle: str) -> str:
    """Lowercase, strip whitespace and a leading @."""
    return handle.strip().lower().lstrip("@")


def find_creator_by_twitter_handle(db: Session, handle: str) -> Optional[Creator]:
    """Return the Creator whose platforms entry matches this Twitter handle, or None."""
    target = normalize_handle(handle)
    if not target:
        return None
    for creator in db.query(Creator).all():
        for platform in creator.platforms or []:
            if platform.get("platform") != "twitter":
                continue
            candidate = normalize_handle(platform.get("handle") or "")
            if candidate == target:
                return creator
    return None


def find_or_create_creator_by_twitter_handle(
    db: Session,
    handle: str,
    display_name: Optional[str] = None,
) -> tuple[Creator, bool]:
    """
    Resolve a Creator by Twitter handle. If none exists, create one with
    tracking_active=False so they're hidden from public lists until reviewed.

    Returns (creator, was_created).
    """
    existing = find_creator_by_twitter_handle(db, handle)
    if existing:
        return existing, False

    normalized = normalize_handle(handle)
    creator = Creator(
        display_name=(display_name or f"@{normalized}").strip(),
        tier=CreatorTier.tracked,
        platforms=[{
            "platform": "twitter",
            "handle": f"@{normalized}",
            "url": f"https://x.com/{normalized}",
        }],
        tracking_active=False,  # soft gate — admin must approve before public
    )
    db.add(creator)
    db.flush()
    log.info(
        "creator_auto_created",
        creator_id=creator.creator_id,
        handle=f"@{normalized}",
        display_name=creator.display_name,
    )
    return creator, True
