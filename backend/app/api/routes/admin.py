"""
Admin tools for retroactively applying ingestion-pipeline improvements.

When the parser, opponent enrichment, or alias map is improved, existing
Source rows still hold the picks they got at first-ingest time. This module
re-runs a URL through the current pipeline without going through the
public /submissions flow (which is rate-limited and Turnstile-gated).

All endpoints require the admin bearer token.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models import Creator, Pick, Source
from app.scrapers.twitter import TwitterScraper
from app.services.creator_lookup import find_or_create_creator_by_twitter_handle
from app.services.record_updater import recompute_record
from app.services.tweet_ingestion import (
    FantasyScorePickRejected,
    ingest_tweet_for_creator,
)

log = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/admin", tags=["admin"])


class ReprocessUrlRequest(BaseModel):
    url: str = Field(min_length=15, max_length=500)


def _canonical_url_variants(url: str) -> list[str]:
    """Return the URL plus its twitter.com / x.com counterpart for dedup lookup."""
    out = {url}
    out.add(url.replace("https://x.com/", "https://twitter.com/"))
    out.add(url.replace("https://twitter.com/", "https://x.com/"))
    return list(out)


@router.post("/reprocess-url")
@limiter.limit("30/minute")
async def reprocess_url(
    request: Request,
    data: ReprocessUrlRequest,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Wipe and re-ingest a single tweet URL through the current pipeline.

    Order of operations:
      1. Fetch the tweet via oEmbed (fail-fast — if X is unreachable or the
         tweet is gone, we don't touch existing data).
      2. Resolve the creator: prefer the prior source's creator_id when the
         URL has been seen before; otherwise auto-create from oEmbed author
         metadata (with tracking_active=False, same as the public flow).
      3. Delete the existing Source + attached Picks for that URL (any
         twitter.com/x.com variant).
      4. Re-run ingest_tweet_for_creator — caption → image-OCR → parse →
         opponent enrichment.
      5. Recompute the creator's record so any deleted resolved picks don't
         leave stale W/L behind.

    Returns the new picks, deleted pick count, and creator info — same
    shape as /submissions plus a deleted_pick_count for visibility.
    """
    url = data.url.strip()

    # 1. Fetch first so we fail before destroying any data.
    scraper = TwitterScraper()
    posts = await scraper.fetch_tweets([url])
    if not posts:
        raise HTTPException(
            status_code=400,
            detail="Could not fetch that tweet — it may be deleted, private, or the URL is wrong.",
        )
    post = posts[0]

    # 2. Determine the creator.
    variants = _canonical_url_variants(post.post_url) + _canonical_url_variants(url)
    existing_source = (
        db.query(Source).filter(Source.post_url.in_(variants)).first()
    )

    creator = None
    if existing_source:
        creator = (
            db.query(Creator)
            .filter(Creator.creator_id == existing_source.creator_id)
            .first()
        )

    if creator is None:
        author_handle = (post.raw or {}).get("author_handle")
        author_name = (post.raw or {}).get("author_name")
        if not author_handle:
            raise HTTPException(
                status_code=400,
                detail="Could not identify the creator behind that post.",
            )
        creator, _was_new = find_or_create_creator_by_twitter_handle(
            db, author_handle, display_name=author_name
        )

    # 3. Delete the prior source + its picks (any URL variant).
    deleted_pick_count = 0
    if existing_source:
        deleted_pick_count = (
            db.query(Pick)
            .filter(Pick.source_id == existing_source.source_id)
            .delete(synchronize_session=False)
        )
        db.delete(existing_source)
        db.flush()
        log.info(
            "admin_reprocess_deleted_existing",
            source_id=existing_source.source_id,
            deleted_picks=deleted_pick_count,
            url=post.post_url,
        )

    # 4. Re-ingest under the current pipeline.
    try:
        result = await ingest_tweet_for_creator(db, post, creator)
    except FantasyScorePickRejected as e:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"Fantasy-score picks are not tracked: {', '.join(e.descriptions)}",
        )
    except Exception as e:
        db.rollback()
        log.error("admin_reprocess_ingest_failed", url=post.post_url, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Reprocessing failed during ingestion. The previous data is still rolled back — try again.",
        )

    # 5. Always recompute, even if the new ingest produced 0 picks.
    recompute_record(creator.creator_id, db)
    db.commit()

    return {
        "url": post.post_url,
        "creator": {
            "creator_id": creator.creator_id,
            "display_name": creator.display_name,
            "tracking_active": creator.tracking_active,
        },
        "deleted_pick_count": deleted_pick_count,
        "new_pick_count": result.picks_extracted,
        "already_tracked": result.already_tracked,
        "picks": result.picks,
    }
