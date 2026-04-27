"""
Scrape endpoint — admin-only batch submission of tweet URLs for an explicit creator.

For anonymous user-driven submissions, see /api/v1/submissions instead.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import require_admin
from app.database import get_db
from app.models import Creator
from app.scrapers.twitter import TwitterScraper
from app.services.tweet_ingestion import (
    FantasyScorePickRejected,
    ingest_tweet_for_creator,
)

log = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/scrape", tags=["scrape"])


class TweetSubmission(BaseModel):
    creator_id: str
    urls: list[str] = Field(max_length=20)


@router.post("/tweets")
@limiter.limit("30/minute")
async def scrape_tweets(
    request: Request,
    data: TweetSubmission,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Admin: submit tweet URLs for a known creator and store the parsed picks."""
    creator = db.query(Creator).filter(Creator.creator_id == data.creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    if not data.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")

    scraper = TwitterScraper()
    posts = await scraper.fetch_tweets(data.urls)

    new_sources = 0
    new_picks = 0
    skipped_existing = 0
    skipped_fantasy_score = []
    pick_details = []

    for post in posts:
        # Savepoint so a per-tweet rejection (e.g. fantasy-score) can be rolled
        # back without nuking the rest of the batch's pending writes.
        sp = db.begin_nested()
        try:
            result = await ingest_tweet_for_creator(db, post, creator)
            sp.commit()
        except FantasyScorePickRejected as e:
            sp.rollback()
            skipped_fantasy_score.append({"url": post.post_url, "props": e.descriptions})
            continue
        if result.already_tracked:
            skipped_existing += 1
            continue
        if result.new_source:
            new_sources += 1
        new_picks += result.picks_extracted
        pick_details.extend(result.picks)

    db.commit()

    return {
        "creator_id": data.creator_id,
        "display_name": creator.display_name,
        "urls_submitted": len(data.urls),
        "tweets_fetched": len(posts),
        "new_sources": new_sources,
        "new_picks": new_picks,
        "skipped_existing": skipped_existing,
        "skipped_fantasy_score": skipped_fantasy_score,
        "picks": pick_details,
    }
