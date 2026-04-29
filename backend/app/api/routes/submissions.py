"""
Anonymous user-driven pick submissions.

Users paste an X (Twitter) post URL. We fetch the tweet via oEmbed,
auto-create the creator if we don't already track them, run the post
through caption -> image-OCR -> parse_picks, and return a shaped result.

Anti-spam (defense in depth, since the endpoint is unauthenticated):
  1. Honeypot field — silently accepts and discards bot-filled forms.
  2. Cloudflare Turnstile — server-side token verification.
  3. Per-IP rate limit — 10/hour via slowapi.
  4. URL pattern check, then live oEmbed fetch as the authoritative validator.
"""
import re
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.scrapers.twitter import TwitterScraper
from app.services.creator_lookup import find_or_create_creator_by_twitter_handle
from app.services.tweet_ingestion import (
    FantasyScorePickRejected,
    ingest_tweet_for_creator,
)
from app.services.turnstile import verify_turnstile_token
from app.posthog_client import posthog_client

log = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/submissions", tags=["submissions"])

# X / Twitter status URL — the only thing we accept.
TWEET_URL_PATTERN = re.compile(
    r"^https?://(?:www\.|mobile\.)?(?:twitter\.com|x\.com)"
    r"/[A-Za-z0-9_]{1,15}/status/\d+(?:[/?#].*)?$"
)


class PickSubmission(BaseModel):
    url: str = Field(min_length=15, max_length=500)
    turnstile_token: Optional[str] = Field(default=None, max_length=4096)
    # Hidden form field. Real users never fill it. Bots that auto-fill all
    # fields will. If non-empty, we drop the submission silently.
    website: Optional[str] = Field(default=None, max_length=200)


@router.post("")
@limiter.limit("10/hour")
async def submit_pick(
    request: Request,
    data: PickSubmission,
    db: Session = Depends(get_db),
):
    # 1. Honeypot — silently accept so we don't tip off the bot.
    if data.website:
        log.info("submission_honeypot_triggered", ip=get_remote_address(request))
        return _silent_ok()

    # 2. URL shape — cheap, fails before any network call.
    url = data.url.strip()
    if not TWEET_URL_PATTERN.match(url):
        raise HTTPException(
            status_code=400,
            detail="Please paste a valid X (Twitter) post URL.",
        )

    # 3. Turnstile — required.
    try:
        verified = await verify_turnstile_token(
            data.turnstile_token or "",
            remote_ip=get_remote_address(request),
        )
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="Submissions are not configured. Please try again later.",
        )
    if not verified:
        raise HTTPException(
            status_code=400,
            detail="Could not verify your submission. Please refresh and try again.",
        )

    # 4. Fetch the tweet — authoritative validator that the URL points at a
    #    real, accessible post.
    scraper = TwitterScraper()
    posts = await scraper.fetch_tweets([url])
    if not posts:
        raise HTTPException(
            status_code=400,
            detail="We couldn't load that post. It may be deleted, private, or the URL may be wrong.",
        )
    post = posts[0]

    author_handle = (post.raw or {}).get("author_handle")
    author_name = (post.raw or {}).get("author_name")
    if not author_handle:
        log.error("submission_missing_author_handle", url=url)
        raise HTTPException(
            status_code=400,
            detail="We couldn't identify the creator behind that post.",
        )

    # 5. Resolve or auto-create the creator (soft-gated: tracking_active=False).
    creator, was_new_creator = find_or_create_creator_by_twitter_handle(
        db, author_handle, display_name=author_name,
    )

    # 6. Ingest — produces Source + Pick rows, or signals "already tracked".
    try:
        result = await ingest_tweet_for_creator(db, post, creator)
        db.commit()
    except FantasyScorePickRejected as e:
        db.rollback()
        if posthog_client:
            posthog_client.capture(
                distinct_id=author_handle,
                event="fantasy pick rejected",
                properties={
                    "creator_handle": author_handle,
                    "prop_count": len(e.descriptions),
                    "$process_person_profile": False,
                },
            )
        raise HTTPException(
            status_code=422,
            detail=(
                "We don't currently track fantasy-score picks (e.g., Hitter FS, "
                "Pitcher FS, Fantasy Score). The points formula varies by book, "
                "so outcomes can't be resolved reliably."
            ),
        )
    except Exception as e:
        db.rollback()
        log.error("submission_ingest_failed", url=url, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while saving your submission. Please try again.",
        )

    if posthog_client:
        if was_new_creator:
            posthog_client.capture(
                distinct_id=author_handle,
                event="creator discovered",
                properties={
                    "creator_handle": author_handle,
                    "$process_person_profile": False,
                },
            )
        if result.already_tracked:
            posthog_client.capture(
                distinct_id=author_handle,
                event="pick already tracked",
                properties={
                    "creator_handle": author_handle,
                    "picks_count": result.picks_extracted,
                    "$process_person_profile": False,
                },
            )
        elif result.needs_review:
            posthog_client.capture(
                distinct_id=author_handle,
                event="pick needs review",
                properties={
                    "creator_handle": author_handle,
                    "picks_parsed": len(result.unpinned_picks),
                    "was_new_creator": was_new_creator,
                    "$process_person_profile": False,
                },
            )
        elif result.picks_extracted > 0:
            posthog_client.capture(
                distinct_id=author_handle,
                event="pick submitted",
                properties={
                    "creator_handle": author_handle,
                    "picks_extracted": result.picks_extracted,
                    "was_new_creator": was_new_creator,
                    "$process_person_profile": False,
                },
            )

    if result.needs_review:
        status = "needs_review"
    elif result.already_tracked:
        status = "already_tracked"
    else:
        status = "received"

    return {
        "status": status,
        "message": _user_message(result, was_new_creator),
        "creator": {
            "display_name": creator.display_name,
            "handle": author_handle,
            "was_new": was_new_creator,
            "pending_review": not creator.tracking_active,
        },
        "picks_extracted": result.picks_extracted,
        "picks": result.picks,
        # Populated only when status == "needs_review": the parser found picks
        # but we couldn't pin them to a scheduled game. Surfacing them lets the
        # user see what we saw while admin review is pending.
        "unpinned_picks": result.unpinned_picks,
    }


def _silent_ok() -> dict:
    """Honeypot response — looks like a normal success to the bot."""
    return {
        "status": "received",
        "message": "Thanks — your submission was received.",
        "creator": None,
        "picks_extracted": 0,
        "picks": [],
        "unpinned_picks": [],
    }


def _user_message(result, was_new_creator: bool) -> str:
    if result.already_tracked:
        if result.picks_extracted == 1:
            return "We already have this post — it's tracking 1 pick."
        return f"We already have this post — it's tracking {result.picks_extracted} picks."
    if result.needs_review:
        # Parsed at least one pick but couldn't match it to a scheduled game.
        # Better to flag for admin review than log a pick we can't resolve.
        return (
            "Thanks — submission received. We couldn't match this to a scheduled "
            "game, so it's queued for review before being added to the record."
        )
    if result.picks_extracted == 0:
        if was_new_creator:
            return (
                "Got it. We didn't find a betting pick in this post, but we've added "
                "the creator for review."
            )
        return "Got it. We didn't find a betting pick in this post."
    pick_word = "pick" if result.picks_extracted == 1 else "picks"
    if was_new_creator:
        return (
            f"Thanks! We logged {result.picks_extracted} {pick_word} and added the "
            "creator for review."
        )
    return f"Thanks! We logged {result.picks_extracted} {pick_word}."
