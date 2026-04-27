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
from app.services.espn_stats import find_opponent_in_schedule, get_scheduled_games
from app.services.odds_api import find_odds_for_pick, get_odds_for_sport

log = structlog.get_logger()

# Below this score we discard parser output.
MIN_PICK_CONFIDENCE = 0.5

# If the parser returns one of these as `event` (or as part of it) we treat it
# as a placeholder and trigger opponent lookup against The Odds API.
_PLACEHOLDER_TOKENS = {"opponent", "tbd", "unknown", "other", "n/a"}


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

    if parsed_picks:
        await _enrich_with_opponents(parsed_picks)
        await _enrich_with_odds(parsed_picks)

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


# ---------------------------------------------------------------------------
# Opponent enrichment
# ---------------------------------------------------------------------------

async def _enrich_with_opponents(picks: list[ParsedPick]) -> None:
    """
    For picks where the parser only captured one team (or wrote a placeholder
    like "Cavs vs Opponent"), look up the matchup in The Odds API and fill it
    in. Mutates picks in place. Also enriches parlay legs.

    Groups by sport so we make at most one upcoming-games request per sport.
    """
    sports_needed: set[str] = set()
    for pick in picks:
        if pick.sport and _event_needs_opponent(pick.event, _team_from_pick(pick)):
            sports_needed.add(pick.sport)
        if pick.pick_type == "parlay":
            for leg in (pick.pick_detail or {}).get("legs", []) or []:
                sport = leg.get("sport")
                team = _team_from_leg(leg)
                if sport and _event_needs_opponent(leg.get("event"), team):
                    sports_needed.add(sport)

    if not sports_needed:
        return

    games_by_sport = {}
    for sport in sports_needed:
        games_by_sport[sport] = await get_scheduled_games(sport)

    for pick in picks:
        if pick.sport:
            team = _team_from_pick(pick)
            if team and _event_needs_opponent(pick.event, team):
                _fill_event_from_lookup(pick, team, games_by_sport.get(pick.sport, []))

        if pick.pick_type == "parlay":
            for leg in (pick.pick_detail or {}).get("legs", []) or []:
                sport = leg.get("sport")
                team = _team_from_leg(leg)
                if sport and team and _event_needs_opponent(leg.get("event"), team):
                    games = games_by_sport.get(sport, [])
                    found = find_opponent_in_schedule(team, games)
                    if found:
                        matched, opponent, _commence = found
                        leg["event"] = f"{matched} vs {opponent}"
                        # Normalize the leg's team to the canonical short name too
                        leg_detail = leg.get("detail")
                        if isinstance(leg_detail, dict) and leg_detail.get("team"):
                            leg_detail["team"] = matched


def _event_needs_opponent(event: Optional[str], team: Optional[str]) -> bool:
    """True if `event` is missing, has a placeholder, or names only one team."""
    if not event:
        return bool(team)  # we can only enrich if we know the pick's team
    cleaned = event.strip().lower()
    if any(token in cleaned for token in _PLACEHOLDER_TOKENS):
        return True
    # No "vs" / "@" → only one team
    return " vs " not in cleaned and " vs. " not in cleaned and " @ " not in cleaned


def _team_from_pick(pick: ParsedPick) -> Optional[str]:
    """Pull the team name from the pick. Falls back to parsing the event string."""
    detail = pick.pick_detail or {}
    team = detail.get("team")
    if team:
        return str(team).strip()
    if pick.event:
        # Strip placeholder tokens, keep the real team name
        first = pick.event.split(" vs ")[0].split(" @ ")[0].strip()
        if first.lower() not in _PLACEHOLDER_TOKENS:
            return first
    return None


def _team_from_leg(leg: dict) -> Optional[str]:
    detail = leg.get("detail") or {}
    team = detail.get("team")
    if team:
        return str(team).strip()
    event = leg.get("event")
    if event:
        first = event.split(" vs ")[0].split(" @ ")[0].strip()
        if first.lower() not in _PLACEHOLDER_TOKENS:
            return first
    return None


def _fill_event_from_lookup(pick: ParsedPick, team: str, games: list) -> None:
    found = find_opponent_in_schedule(team, games)
    if not found:
        return
    matched, opponent, commence_time = found
    # Use canonical short names (e.g. "Avalanche" not "Avs") so display,
    # event string, and outcome-resolution lookups all agree.
    pick.event = f"{matched} vs {opponent}"
    if isinstance(pick.pick_detail, dict) and pick.pick_detail.get("team"):
        pick.pick_detail["team"] = matched
    # If the parser didn't pick up an event_date, we now have one for free —
    # use the game's commence time so outcome resolution can match later.
    if pick.event_date is None:
        pick.event_date = commence_time


# ---------------------------------------------------------------------------
# Odds enrichment
# ---------------------------------------------------------------------------

async def _enrich_with_odds(picks: list[ParsedPick]) -> None:
    """
    Fill in `pick.odds` for picks where the LLM parser didn't find a price
    in the post text. Calls The Odds API once per sport that needs lookup.

    Self-throttles via odds_api.check_budget() — when the monthly budget is
    near zero the lookup quietly returns None and the pick stays unpriced
    rather than blowing the 450/month free-tier cap.

    Skips parlays (parlay-level odds usually come from the post itself).
    """
    sports_needed = {
        p.sport for p in picks
        if p.sport
        and p.odds is None
        and p.pick_type in ("moneyline", "spread", "over_under")
    }
    if not sports_needed:
        return

    odds_by_sport: dict[str, list[dict]] = {}
    for sport in sports_needed:
        odds_by_sport[sport] = await get_odds_for_sport(sport)

    for pick in picks:
        if pick.odds is not None or pick.sport not in odds_by_sport:
            continue
        team = (pick.pick_detail or {}).get("team") if isinstance(pick.pick_detail, dict) else None
        odds = find_odds_for_pick(
            team=team,
            pick_type=pick.pick_type,
            pick_detail=pick.pick_detail or {},
            games=odds_by_sport[pick.sport],
        )
        if odds:
            pick.odds = odds
            log.info("odds_filled", sport=pick.sport, team=team, odds=odds, pick_type=pick.pick_type)
