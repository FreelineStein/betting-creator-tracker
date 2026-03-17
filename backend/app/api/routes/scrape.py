"""
Scrape endpoint — submit tweet URLs for extraction and pick parsing.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models import (
    Creator, Source, Pick, ExtractionStatus, PickStatus, ExtractionMethod,
)
from app.scrapers.twitter import TwitterScraper, extract_image_url, extract_text_from_image
from app.pipeline.parser import parse_picks
from app.api.deps import require_admin

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
    """
    Submit tweet URLs for a creator. Fetches text via oEmbed,
    parses picks via LLM, and stores results.
    """
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
    pick_details = []
    errors = []

    for post in posts:
        existing = db.query(Source).filter(Source.post_url == post.post_url).first()
        if existing:
            # If the source exists but produced no picks, delete it and re-process
            existing_picks = db.query(Pick).filter(Pick.source_id == existing.source_id).count()
            if existing_picks > 0:
                skipped_existing += 1
                continue
            log.info("Re-processing source with zero picks", url=post.post_url)
            db.delete(existing)
            db.flush()

        source = Source(
            creator_id=creator.creator_id,
            platform="twitter",
            post_type="tweet",
            post_url=post.post_url,
            posted_at=post.posted_at,
        )
        db.add(source)
        db.flush()
        new_sources += 1

        # Step 1: Try caption text first
        extracted_text = post.caption
        extraction_method = ExtractionMethod.caption
        parsed_picks = []

        source.extraction_attempts = [{"method": "caption", "success": bool(extracted_text), "confidence": 1.0}]

        if extracted_text:
            try:
                parsed_picks = await parse_picks(extracted_text, source_url=post.post_url)
            except Exception as e:
                log.error("Caption parse failed", url=post.post_url, error=str(e))
                errors.append({"url": post.post_url, "error": f"caption parse: {e}"})

        # Step 2: If no picks from caption, try image extraction
        if not parsed_picks:
            try:
                image_url = await extract_image_url(post.post_url)
                if image_url:
                    log.info("No picks in caption, trying image", url=post.post_url)
                    image_text = await extract_text_from_image(image_url)
                    source.extraction_attempts.append({
                        "method": "image_vision",
                        "success": bool(image_text),
                        "confidence": 0.85,
                        "image_url": image_url,
                    })

                    if image_text:
                        extracted_text = image_text
                        extraction_method = ExtractionMethod.ocr
                        try:
                            parsed_picks = await parse_picks(image_text, source_url=post.post_url)
                        except Exception as e:
                            log.error("Image parse failed", url=post.post_url, error=str(e))
                            errors.append({"url": post.post_url, "error": f"image parse: {e}"})
            except Exception as e:
                log.error("Image extraction failed", url=post.post_url, error=str(e))

        source.raw_content = extracted_text
        source.extraction_status = (
            ExtractionStatus.success if parsed_picks else
            ExtractionStatus.needs_review if extracted_text else
            ExtractionStatus.failed
        )

        # Step 3: Store parsed picks
        for parsed in parsed_picks:
            pick = Pick(
                source_id=source.source_id,
                creator_id=creator.creator_id,
                sport=parsed.sport,
                event=parsed.event,
                event_date=parsed.event_date,
                pick_type=parsed.pick_type,
                pick_detail=parsed.pick_detail,
                odds=parsed.odds,
                units=parsed.units,
                status=PickStatus.pending,
                extraction_method=extraction_method,
                extraction_confidence=parsed.confidence,
                raw_text=parsed.raw_text,
            )
            db.add(pick)
            new_picks += 1
            pick_details.append({
                "source": extraction_method.value,
                "sport": parsed.sport,
                "event": parsed.event,
                "pick_type": parsed.pick_type,
                "pick_detail": parsed.pick_detail,
                "odds": parsed.odds,
                "confidence": parsed.confidence,
            })

    db.commit()

    return {
        "creator_id": data.creator_id,
        "display_name": creator.display_name,
        "urls_submitted": len(data.urls),
        "tweets_fetched": len(posts),
        "new_sources": new_sources,
        "new_picks": new_picks,
        "skipped_existing": skipped_existing,
        "picks": pick_details,
        "errors": errors,
    }
