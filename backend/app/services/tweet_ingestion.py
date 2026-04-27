"""
Shared tweet-ingestion service.

Takes a fetched RawPost (from TwitterScraper) and a Creator, and runs the
caption -> image-OCR -> parse_picks flow that produces Source + Pick rows.

Called from:
- /scrape/tweets (admin batch endpoint)
- /submissions   (anonymous single-URL endpoint)

Dedup: Source.post_url is the unique key. If a Source already exists with
picks attached, we report "already_tracked" so callers can surface that to
the user. If a Source exists with zero picks (a prior failed extraction),
we delete it and retry — same behavior the scrape route had inline.
"""
from dataclasses import dataclass, field
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.models import (
    Creator,
    ExtractionMethod,
    ExtractionStatus,
    Pick,
    PickStatus,
    Source,
)
from app.pipeline.parser import ParsedPick, parse_picks
from app.scrapers.base import RawPost
from app.scrapers.twitter import extract_image_url, extract_text_from_image

log = structlog.get_logger()

# Below this score we discard parser output.
MIN_PICK_CONFIDENCE = 0.5


@dataclass
class TweetIngestionResult:
    """What happened when we tried to ingest a single tweet."""
    post_url: str
    new_source: bool = False
    already_tracked: bool = False         # source existed AND had picks
    picks_extracted: int = 0
    picks: list[dict] = field(default_factory=list)
    error: Optional[str] = None


async def ingest_tweet_for_creator(
    db: Session,
    post: RawPost,
    creator: Creator,
) -> TweetIngestionResult:
    """
    Persist a fetched tweet as Source + Pick rows for `creator`.

    Caller is responsible for:
      - Calling db.commit() (we only flush)
      - Rolling back on exception

    Returns a TweetIngestionResult so callers can shape user-facing responses.
    """
    result = TweetIngestionResult(post_url=post.post_url)

    existing = db.query(Source).filter(Source.post_url == post.post_url).first()
    if existing:
        existing_pick_count = (
            db.query(Pick).filter(Pick.source_id == existing.source_id).count()
        )
        if existing_pick_count > 0:
            result.already_tracked = True
            result.picks_extracted = existing_pick_count
            return result
        # Source exists but failed to extract anything before — retry it.
        log.info("retrying_source_with_zero_picks", url=post.post_url)
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
    result.new_source = True

    parsed_picks, extraction_method, extracted_text = await _extract_picks(post, source)

    source.raw_content = extracted_text
    source.extraction_status = (
        ExtractionStatus.success if parsed_picks
        else ExtractionStatus.needs_review if extracted_text
        else ExtractionStatus.failed
    )

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
        result.picks_extracted += 1
        result.picks.append({
            "source": extraction_method.value,
            "sport": parsed.sport,
            "event": parsed.event,
            "pick_type": parsed.pick_type,
            "pick_detail": parsed.pick_detail,
            "odds": parsed.odds,
            "confidence": parsed.confidence,
        })

    return result


async def _extract_picks(
    post: RawPost, source: Source,
) -> tuple[list[ParsedPick], ExtractionMethod, Optional[str]]:
    """
    Try caption text first; fall back to image OCR via Claude vision.
    Returns (picks, method_used, extracted_text).
    """
    extracted_text = post.caption
    extraction_method = ExtractionMethod.caption
    parsed_picks: list[ParsedPick] = []
    source.extraction_attempts = [
        {"method": "caption", "success": bool(extracted_text), "confidence": 1.0}
    ]

    if extracted_text:
        try:
            parsed_picks = await parse_picks(extracted_text, source_url=post.post_url)
        except Exception as e:
            log.error("caption_parse_failed", url=post.post_url, error=str(e))

    parsed_picks = _filter_low_quality(parsed_picks)

    if parsed_picks:
        return parsed_picks, extraction_method, extracted_text

    # Caption produced nothing useful — try the image attached to the tweet.
    try:
        image_url = await extract_image_url(post.post_url)
        if not image_url:
            return parsed_picks, extraction_method, extracted_text

        log.info("trying_image_extraction", url=post.post_url)
        image_text = await extract_text_from_image(image_url)
        source.extraction_attempts.append({
            "method": "image_vision",
            "success": bool(image_text),
            "confidence": 0.85,
            "image_url": image_url,
        })
        if not image_text:
            return parsed_picks, extraction_method, extracted_text

        extracted_text = image_text
        extraction_method = ExtractionMethod.ocr
        try:
            parsed_picks = _filter_low_quality(
                await parse_picks(image_text, source_url=post.post_url)
            )
        except Exception as e:
            log.error("image_parse_failed", url=post.post_url, error=str(e))
    except Exception as e:
        log.error("image_extraction_failed", url=post.post_url, error=str(e))

    return parsed_picks, extraction_method, extracted_text


def _filter_low_quality(picks: list[ParsedPick]) -> list[ParsedPick]:
    """Drop low-confidence picks and empty parlay shells."""
    return [
        p for p in picks
        if p.confidence >= MIN_PICK_CONFIDENCE
        and not (p.pick_type == "parlay" and not p.pick_detail.get("legs"))
    ]
