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
from app.models import Creator, ExtractionStatus, Pick, Source
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


class DebugParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


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
        # Diagnostic surface — without this we can't tell from a curl whether
        # `new_pick_count: 0` means the parser returned nothing or means
        # parsed picks couldn't be pinned to a scheduled game.
        "needs_review": result.needs_review,
        "unpinned_picks": result.unpinned_picks,
        "pin_fallback": result.pin_fallback,
        "picks": result.picks,
    }


# ---------------------------------------------------------------------------
# debug-parse — call the LLM parser directly on raw text and return the raw
# response so we can see no_picks_reason and the picks-before-validation when
# diagnosing why a submission doesn't extract anything.
# ---------------------------------------------------------------------------

@router.post("/debug-parse")
@limiter.limit("30/minute")
async def debug_parse(
    request: Request,
    data: DebugParseRequest,
    _admin: str = Depends(require_admin),
):
    """
    Run a single chunk of text through the parser's LLM call and echo the
    raw structured output. No DB writes, no scrapes — just `text in, JSON
    out` so we can see what the parser actually thinks.

    Useful when a submission lands in needs_review with zero picks and the
    only feedback is silence — this surfaces `no_picks_reason` and the
    pre-validation pick list.
    """
    from app.pipeline.parser import _deserialize_picks, _llm_parse

    try:
        raw = await _llm_parse(data.text)
    except Exception as e:
        log.error("debug_parse_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Parser call failed: {e}")

    raw_picks = raw.get("picks", []) or []
    deserialized = _deserialize_picks(raw_picks, data.text)
    return {
        "no_picks_reason": raw.get("no_picks_reason"),
        "raw_picks": raw_picks,
        "deserialized_count": len(deserialized),
        "deserialized": [
            {
                "sport": p.sport,
                "league": p.league,
                "event": p.event,
                "pick_type": p.pick_type,
                "pick_detail": p.pick_detail,
                "odds": p.odds,
                "confidence": p.confidence,
            }
            for p in deserialized
        ],
    }


# ---------------------------------------------------------------------------
# needs_review queue
# ---------------------------------------------------------------------------

@router.get("/needs-review")
@limiter.limit("60/minute")
async def list_needs_review(
    request: Request,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    List sources parked at extraction_status=needs_review.

    These are submissions where parsing succeeded but at least one pick
    couldn't be pinned to a scheduled ESPN game (or, on legacy data,
    where extraction produced no picks but text was present). No Pick
    rows exist for them yet; admin reviews and either approves (force-
    ingest without the pinning gate) or deletes.
    """
    sources = (
        db.query(Source)
        .filter(Source.extraction_status == ExtractionStatus.needs_review)
        .order_by(Source.scraped_at.asc())
        .all()
    )
    out = []
    for s in sources:
        creator = (
            db.query(Creator).filter(Creator.creator_id == s.creator_id).first()
        )
        out.append({
            "source_id": s.source_id,
            "post_url": s.post_url,
            "posted_at": s.posted_at.isoformat() if s.posted_at else None,
            "scraped_at": s.scraped_at.isoformat() if s.scraped_at else None,
            "raw_content": s.raw_content,
            "extraction_attempts": s.extraction_attempts,
            "creator": {
                "creator_id": creator.creator_id if creator else None,
                "display_name": creator.display_name if creator else None,
                "tracking_active": creator.tracking_active if creator else None,
            },
        })
    return {"count": len(out), "sources": out}


@router.post("/sources/{source_id}/approve")
@limiter.limit("30/minute")
async def approve_source(
    request: Request,
    source_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Force-ingest a needs_review source, bypassing the pinning gate.

    Re-fetches the tweet (so this works even if the DB only has
    partial state), runs the current parser + enrichment, and creates
    Pick rows for every parsed pick — even ones without `event_id`.
    Unpinned picks fall through to the resolver's legacy fuzzy-match
    branch.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")
    if source.extraction_status != ExtractionStatus.needs_review:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Source is not in needs_review (current: "
                f"{source.extraction_status.value}); refusing to approve."
            ),
        )

    creator = db.query(Creator).filter(Creator.creator_id == source.creator_id).first()
    if not creator:
        raise HTTPException(status_code=500, detail="Source has no creator.")

    scraper = TwitterScraper()
    posts = await scraper.fetch_tweets([source.post_url])
    if not posts:
        raise HTTPException(
            status_code=400,
            detail="Could not refetch the tweet — it may be deleted, private, or the URL changed.",
        )
    post = posts[0]

    # The existing source row will be deleted-and-replaced by
    # ingest_tweet_for_creator's "source exists with zero picks" branch.
    try:
        result = await ingest_tweet_for_creator(
            db, post, creator, enforce_pinning=False,
        )
    except FantasyScorePickRejected as e:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"Fantasy-score picks are not tracked: {', '.join(e.descriptions)}",
        )
    except Exception as e:
        db.rollback()
        log.error("admin_approve_ingest_failed", source_id=source_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Approval failed during ingestion. Source untouched — try again.",
        )

    recompute_record(creator.creator_id, db)
    db.commit()

    return {
        "source_id": source_id,
        "url": post.post_url,
        "creator": {
            "creator_id": creator.creator_id,
            "display_name": creator.display_name,
        },
        "new_pick_count": result.picks_extracted,
        "picks": result.picks,
    }


# ---------------------------------------------------------------------------
# user-flagged review queue
# ---------------------------------------------------------------------------

@router.get("/flagged")
@limiter.limit("60/minute")
async def list_flagged(
    request: Request,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    List sources a user flagged with "picks don't look right".

    Independent of the needs_review queue — these submissions parsed +
    pinned fine according to the pipeline, but the user told us the
    output doesn't match the post. Typical cleanup is to reprocess after
    a parser fix or to surgically correct via the picks endpoints.
    """
    sources = (
        db.query(Source)
        .filter(Source.flagged_for_review == True)  # noqa: E712 — SA needs ==
        .order_by(Source.scraped_at.desc())
        .all()
    )
    out = []
    for s in sources:
        creator = (
            db.query(Creator).filter(Creator.creator_id == s.creator_id).first()
        )
        picks = (
            db.query(Pick).filter(Pick.source_id == s.source_id)
            .order_by(Pick.logged_at.asc())
            .all()
        )
        out.append({
            "source_id": s.source_id,
            "post_url": s.post_url,
            "posted_at": s.posted_at.isoformat() if s.posted_at else None,
            "scraped_at": s.scraped_at.isoformat() if s.scraped_at else None,
            "extraction_status": s.extraction_status.value if s.extraction_status else None,
            "creator": {
                "creator_id": creator.creator_id if creator else None,
                "display_name": creator.display_name if creator else None,
            },
            "picks": [
                {
                    "pick_id": p.pick_id,
                    "sport": p.sport,
                    "league": p.league,
                    "event": p.event,
                    "pick_type": p.pick_type,
                    "pick_detail": p.pick_detail,
                    "odds": p.odds,
                    "status": p.status.value if p.status else None,
                }
                for p in picks
            ],
        })
    return {"count": len(out), "sources": out}


@router.post("/sources/{source_id}/unflag")
@limiter.limit("30/minute")
async def unflag_source(
    request: Request,
    source_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Clear the user-flagged bit after a flag has been triaged."""
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")
    source.flagged_for_review = False
    db.commit()
    return {"source_id": source_id, "flagged_for_review": False}


@router.delete("/sources/{source_id}")
@limiter.limit("30/minute")
async def delete_source(
    request: Request,
    source_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Drop a parked source (and any picks attached, defensively).

    Only accepts sources currently at needs_review — for general source
    deletion use the picks-side cleanup scripts. Recomputes the creator's
    record afterward, since attached picks (if any) influenced totals.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")
    if source.extraction_status != ExtractionStatus.needs_review:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Source is not in needs_review (current: "
                f"{source.extraction_status.value}); refusing to delete via this endpoint."
            ),
        )

    creator_id = source.creator_id
    deleted_picks = (
        db.query(Pick).filter(Pick.source_id == source.source_id)
        .delete(synchronize_session=False)
    )
    db.delete(source)
    db.flush()
    if creator_id:
        recompute_record(creator_id, db)
    db.commit()

    return {
        "source_id": source_id,
        "deleted_picks": deleted_picks,
    }
