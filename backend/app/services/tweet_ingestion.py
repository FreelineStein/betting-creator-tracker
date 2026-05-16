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
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
from app.services.espn_stats import (
    _normalize_team_query,
    _word_match,
    find_opponent_in_schedule,
    get_scheduled_games,
)
from app.services.odds_api import find_odds_for_pick, get_odds_for_sport
from app.services.outcome_resolver import parlay_all_legs_unresolvable
from app.posthog_client import posthog_client

log = structlog.get_logger()

# Below this score we discard parser output.
MIN_PICK_CONFIDENCE = 0.5

# If the parser returns one of these as `event` (or as part of it) we treat it
# as a placeholder and trigger opponent lookup against The Odds API.
_PLACEHOLDER_TOKENS = {"opponent", "tbd", "unknown", "other", "n/a"}

# PrizePicks/Underdog/Sleeper "fantasy score" props use a points formula that
# varies by book. We can't resolve them reliably, so we reject the whole
# submission rather than log picks that will sit pending forever.
# Word-boundary on "FS" so we don't false-positive on words like "Faceoffs".
_FANTASY_SCORE_PATTERN = re.compile(r"\bFS\b|fantasy\s+(?:score|points)", re.IGNORECASE)


class FantasyScorePickRejected(Exception):
    """Submission contained a fantasy-score prop we don't track."""

    def __init__(self, descriptions: list[str]):
        self.descriptions = descriptions
        super().__init__(
            f"Fantasy-score picks are not tracked: {', '.join(descriptions)}"
        )


def _is_fantasy_score_prop(prop: object) -> bool:
    if not isinstance(prop, str) or not prop:
        return False
    return bool(_FANTASY_SCORE_PATTERN.search(prop))


def _find_fantasy_score_props(picks: list["ParsedPick"]) -> list[str]:
    """Return human-readable descriptions of any FS-style props in the list."""
    matches: list[str] = []
    for pick in picks:
        if pick.pick_type == "prop":
            detail = pick.pick_detail or {}
            if _is_fantasy_score_prop(detail.get("prop")):
                matches.append(f"{detail.get('player', '?')} {detail.get('prop', '')}")
        elif pick.pick_type == "parlay":
            for leg in (pick.pick_detail or {}).get("legs", []) or []:
                if leg.get("type") != "prop":
                    continue
                leg_detail = leg.get("detail") or {}
                if _is_fantasy_score_prop(leg_detail.get("prop")):
                    matches.append(
                        f"{leg_detail.get('player', '?')} {leg_detail.get('prop', '')}"
                    )
    return matches


@dataclass
class TweetIngestionResult:
    """What happened when we tried to ingest a single tweet."""
    post_url: str
    # Set once the Source row exists — populated both for new ingestions and
    # already_tracked dedup hits, so callers can hand the user a stable id
    # they can later flag for manual review.
    source_id: Optional[str] = None
    new_source: bool = False
    already_tracked: bool = False         # source existed AND had picks
    picks_extracted: int = 0
    picks: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    # True when picks were parsed but at least one couldn't be pinned to a
    # scheduled ESPN game. The Source is logged with extraction_status
    # `needs_review`, no Pick rows are created, and the user is told their
    # submission is awaiting review.
    needs_review: bool = False
    # Human-readable list of picks the user submitted, even when nothing was
    # logged — so the review-pending UI can show what the parser saw.
    unpinned_picks: list[dict] = field(default_factory=list)
    # Diagnostic: did the LLM pin fallback run, and what did it do? Surface
    # in admin reprocess responses so we can see when it's silently failing.
    pin_fallback: Optional[dict] = None


async def ingest_tweet_for_creator(
    db: Session,
    post: RawPost,
    creator: Creator,
    *,
    enforce_pinning: bool = True,
) -> TweetIngestionResult:
    """
    Persist a fetched tweet as Source + Pick rows for `creator`.

    Caller is responsible for:
      - Calling db.commit() (we only flush)
      - Rolling back on exception

    `enforce_pinning` (default True): when True, submissions where any
    pick can't be pinned to a scheduled ESPN game are routed to
    needs_review with no Pick rows created. The admin /approve flow
    overrides this to False to log the picks even when ESPN coverage
    is missing — those picks fall through to the resolver's legacy
    fuzzy-match path.

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
            result.source_id = existing.source_id
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
    result.source_id = source.source_id

    parsed_picks, extraction_method, extracted_text = await _extract_picks(post, source)

    if parsed_picks:
        fs_descriptions = _find_fantasy_score_props(parsed_picks)
        if fs_descriptions:
            log.info(
                "submission_rejected_fantasy_score",
                url=post.post_url,
                props=fs_descriptions,
            )
            raise FantasyScorePickRejected(fs_descriptions)
        await _enrich_with_opponents(parsed_picks, posted_at=post.posted_at)
        # Fill market odds at submit time so picks display a price immediately
        # instead of waiting for the closing-odds cron (which only fires within
        # 90 min of game start). Self-throttles via the Odds API budget guard.
        # LLM-extracted odds from the post text are preserved verbatim.
        await _enrich_with_odds(parsed_picks)
        # Last-resort pinning gate: if the team-name lookup left any pick
        # unpinned, ask Claude to bind it to a specific event_id chosen from
        # the candidate scheduled games. Catches SGP+ flattening, special
        # bet types, and player-name-only legs the standard heuristics miss.
        # Hallucination-safe: only event_ids in the candidate list stick.
        if not _all_picks_pinned(parsed_picks):
            from app.services.llm_pin_fallback import pin_unmatched_picks
            try:
                fallback_result = await pin_unmatched_picks(
                    extracted_text or "",
                    parsed_picks,
                    posted_at=post.posted_at,
                )
                result.pin_fallback = fallback_result
                if fallback_result.get("pinned") and posthog_client:
                    posthog_client.capture(
                        distinct_id=creator.creator_id,
                        event="pin fallback used",
                        properties={
                            "pinned": fallback_result["pinned"],
                            "$process_person_profile": False,
                        },
                    )
            except Exception as e:
                log.warning("pin_fallback_call_failed", url=post.post_url, error=str(e))
                result.pin_fallback = {
                    "pinned": 0,
                    "attempted": 0,
                    "candidates": 0,
                    "raw_response": None,
                    "skipped_reason": f"caller_error:{e}",
                }

    source.raw_content = extracted_text

    # Hard gate: if we parsed picks but couldn't pin every one of them to a
    # scheduled ESPN game, route the whole submission to needs_review and
    # don't create any Pick rows. Half-pinned submissions would otherwise
    # leak unresolvable picks into the records, exactly the class of bug the
    # event_id refactor is meant to eliminate.
    #
    # `enforce_pinning=False` is the admin override path (POST /admin/sources/
    # {id}/approve): admin has eyeballed the parked source and decided to log
    # the picks anyway, so unpinned picks fall through to the legacy fuzzy
    # resolver branch.
    needs_review_for_unpinned = (
        enforce_pinning and bool(parsed_picks) and not _all_picks_pinned(parsed_picks)
    )
    if needs_review_for_unpinned:
        source.extraction_status = ExtractionStatus.needs_review
        result.needs_review = True
        result.unpinned_picks = _summarize_unpinned_picks(parsed_picks)
        log.info(
            "submission_unpinned_routed_to_review",
            url=post.post_url,
            picks_parsed=len(parsed_picks),
        )
        return result

    source.extraction_status = (
        ExtractionStatus.success if parsed_picks
        else ExtractionStatus.needs_review if extracted_text
        else ExtractionStatus.failed
    )

    if not parsed_picks and posthog_client:
        # Platforms attached to the creator give useful signal for diagnosing
        # extraction gaps. Safe to log because handles are public identifiers.
        creator_handle = next(
            (p.get("handle") for p in (creator.platforms or []) if p.get("platform") == "twitter"),
            None,
        )
        posthog_client.capture(
            distinct_id=creator_handle or creator.creator_id,
            event="pick extraction failed",
            properties={
                "creator_id": creator.creator_id,
                "extraction_method": extraction_method.value if extraction_method else None,
                "has_caption": bool(post.caption),
                "$process_person_profile": False,
            },
        )

    for parsed in parsed_picks:
        pick = Pick(
            source_id=source.source_id,
            creator_id=creator.creator_id,
            sport=parsed.sport,
            league=parsed.league,
            event=parsed.event,
            event_date=parsed.event_date,
            event_id=parsed.event_id,
            event_provider=parsed.event_provider,
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
            "league": parsed.league,
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
    """
    Drop low-confidence picks and parlay shells the parser couldn't fill.

    Three things get filtered out:
      1. Picks below MIN_PICK_CONFIDENCE.
      2. Parlays with no legs at all (`legs` empty list).
      3. Parlays where every leg has empty detail — the signature of a
         caption that says "5 props in a massive game" but doesn't list
         them. Treating those as "no picks" lets ingestion fall through
         to image OCR, which is where the actual bet-slip data lives.
    """
    keep: list[ParsedPick] = []
    for p in picks:
        if p.confidence < MIN_PICK_CONFIDENCE:
            continue
        if p.pick_type == "parlay":
            legs = (p.pick_detail or {}).get("legs") or []
            if not legs:
                continue
            if parlay_all_legs_unresolvable(legs):
                continue
        keep.append(p)
    return keep


# ---------------------------------------------------------------------------
# Odds enrichment
# ---------------------------------------------------------------------------

async def _enrich_with_odds(picks: list[ParsedPick]) -> None:
    """
    Fill in `pick.odds` for picks where the LLM parser didn't find a price
    in the post text. Calls The Odds API once per sport that needs lookup.

    Self-throttles via odds_api.check_budget() — when the monthly budget is
    near zero the lookup quietly returns nothing and the pick stays unpriced.
    Skips parlay (parlay-level odds usually come from the post itself) and
    prop (no /odds market).
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
        if pick.odds is not None:
            continue
        if pick.sport not in odds_by_sport or not odds_by_sport[pick.sport]:
            continue
        team = (pick.pick_detail or {}).get("team") if isinstance(pick.pick_detail, dict) else None
        # Game-total over/unders carry direction + total but no team, so
        # find_odds_for_pick can't pick a game. Fall back to either side of
        # the event string ("Diamondbacks vs Rockies") since _find_game_for_team
        # matches against both home and away.
        if not team and pick.event:
            for part in pick.event.replace(" vs ", "|").replace(" @ ", "|").replace(" vs. ", "|").split("|"):
                cleaned = part.strip()
                if cleaned:
                    team = cleaned
                    break
        odds = find_odds_for_pick(
            team=team,
            pick_type=pick.pick_type,
            pick_detail=pick.pick_detail or {},
            games=odds_by_sport[pick.sport],
        )
        if odds:
            pick.odds = odds
            log.info("odds_filled_at_submit", sport=pick.sport, team=team, odds=odds, pick_type=pick.pick_type)


# ---------------------------------------------------------------------------
# Opponent enrichment
# ---------------------------------------------------------------------------

async def _enrich_with_opponents(
    picks: list[ParsedPick],
    posted_at: Optional[datetime] = None,
) -> None:
    """
    Pin every pick (and parlay leg) to a specific scheduled ESPN game.

    For each pick with sport + team we hit the ESPN scoreboard window
    (anchor ±1 / +5 days) and, on a match, persist `event_id` + `event_provider`
    so outcome resolution becomes a direct lookup. We also fill in opponent
    when the parser only captured one team, and adopt the game's commence
    time as `event_date` if missing.

    `posted_at` anchors the scoreboard window. For an old tweet (replay via
    /admin/reprocess-url, or a user submitting a historical URL), passing
    "now" would pin to today's slate of games for the same teams instead of
    the one the creator actually picked. Callers should always pass the
    tweet's `posted_at`.

    Groups by sport so we make at most one scoreboard request per sport.

    Picks that don't match any scheduled game are left with `event_id = None`;
    `_all_picks_pinned` detects that and the caller routes the submission to
    needs_review rather than creating an unresolvable Pick row.
    """
    # Collect every (sport, league_hint) the picks need so we can fetch
    # narrower league-specific slates instead of one giant per-sport pull.
    # Each unique combo gets its own scoreboard call (cached by hint key).
    slates_needed: set[tuple[str, Optional[str]]] = set()
    for pick in picks:
        if pick.sport and _team_from_pick(pick):
            slates_needed.add((pick.sport, pick.league))
        if pick.pick_type == "parlay":
            for leg in (pick.pick_detail or {}).get("legs", []) or []:
                sport = leg.get("sport")
                if sport and _team_from_leg(leg):
                    slates_needed.add((sport, leg.get("league")))

    if not slates_needed:
        return

    games_by_key: dict[tuple[str, Optional[str]], list] = {}
    for (sport, hint) in slates_needed:
        games_by_key[(sport, hint)] = await get_scheduled_games(
            sport, anchor_date=posted_at, league_hint=hint,
        )

    for pick in picks:
        # Prefer the parser's date as the pin anchor; fall back to the
        # tweet's posted_at. Resolves MLB/NHL series where the same two
        # teams play on consecutive days — without an anchor the pin
        # search returns the soonest of the candidates and mis-pins to
        # the wrong day.
        pick_anchor = pick.event_date or posted_at
        if pick.sport:
            team = _team_from_pick(pick)
            if team:
                _pin_pick_to_game(
                    pick, team,
                    games_by_key.get((pick.sport, pick.league), []),
                    anchor_date=pick_anchor,
                )

        if pick.pick_type == "parlay":
            for leg in (pick.pick_detail or {}).get("legs", []) or []:
                sport = leg.get("sport")
                team = _team_from_leg(leg)
                if sport and team:
                    _pin_leg_to_game(
                        leg, team,
                        games_by_key.get((sport, leg.get("league")), []),
                        anchor_date=pick_anchor,
                    )


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


def _opponent_from_event(event: Optional[str], team: str) -> Optional[str]:
    """
    When the parsed event names two teams ("TeamA vs TeamB"), return the
    team that isn't `team`. Used to require both-team agreement on the
    pinned matchup — protects against league-mis-hint pin errors like a
    Premier-League-narrowed slate pinning a Chelsea-vs-Man-City FA Cup
    leg to a Chelsea-vs-Tottenham game. Returns None when the event names
    a single team, contains a placeholder, or doesn't include `team`.
    """
    if not event or not team:
        return None
    needle = _normalize_team_query(team)
    if not needle:
        return None
    for sep in (" vs. ", " vs ", " @ "):
        if sep in event:
            a, _mid, b = event.partition(sep)
            a, b = a.strip(), b.strip()
            if not a or not b:
                return None
            if a.lower() in _PLACEHOLDER_TOKENS or b.lower() in _PLACEHOLDER_TOKENS:
                return None
            if _word_match(needle, _normalize_team_query(a)):
                return b
            if _word_match(needle, _normalize_team_query(b)):
                return a
            return None
    return None


def _pin_pick_to_game(
    pick: ParsedPick,
    team: str,
    games: list,
    *,
    anchor_date: Optional[datetime] = None,
) -> None:
    """Pin a pick to its scheduled ESPN game; fill opponent only when missing."""
    found = find_opponent_in_schedule(
        team, games,
        anchor_date=anchor_date,
        opponent_hint=_opponent_from_event(pick.event, team),
    )
    if not found:
        return  # caller detects via missing event_id and routes to needs_review
    matched, opponent, commence_time, game_id, league = found
    pick.event_id = game_id
    pick.event_provider = "espn"
    # Adopt the game's commence time when the parser missed event_date OR
    # when its guess is far from the pinned game (>24h). The parser tends to
    # hallucinate a year for dates like "May 8" — defaulting to the season
    # better-represented in its training data — and a confidently-wrong year
    # would otherwise survive even though we now have the verified ESPN game.
    if pick.event_date is None:
        pick.event_date = commence_time
    else:
        # The parser sometimes emits a date-only string ("2025-05-08") which
        # Pydantic parses as a naive datetime; commence_time from ESPN is
        # always UTC-aware. Treat naive parser dates as UTC for comparison.
        parser_aware = (
            pick.event_date
            if pick.event_date.tzinfo
            else pick.event_date.replace(tzinfo=timezone.utc)
        )
        if abs((parser_aware - commence_time).total_seconds()) > 24 * 3600:
            pick.event_date = commence_time
    # Use canonical short names (e.g. "Avalanche" not "Avs") so display,
    # event string, and outcome-resolution lookups all agree.
    if isinstance(pick.pick_detail, dict) and pick.pick_detail.get("team"):
        pick.pick_detail["team"] = matched
    if _event_needs_opponent(pick.event, team):
        pick.event = f"{matched} vs {opponent}"
    # Scoreboard match is authoritative on which competition this is — for
    # soccer we know the actual league only after pinning, since two EPL
    # teams can also draw each other in Europa knockouts.
    if league and pick.sport == "SOCCER":
        pick.league = league


def _pin_leg_to_game(
    leg: dict,
    team: str,
    games: list,
    *,
    anchor_date: Optional[datetime] = None,
) -> None:
    """Pin a parlay leg to its scheduled ESPN game."""
    found = find_opponent_in_schedule(
        team, games,
        anchor_date=anchor_date,
        opponent_hint=_opponent_from_event(leg.get("event"), team),
    )
    if not found:
        return
    matched, opponent, _commence, game_id, league = found
    leg["event_id"] = game_id
    leg["event_provider"] = "espn"
    if _event_needs_opponent(leg.get("event"), team):
        leg["event"] = f"{matched} vs {opponent}"
    leg_detail = leg.get("detail")
    if isinstance(leg_detail, dict) and leg_detail.get("team"):
        leg_detail["team"] = matched
    if league and leg.get("sport") == "SOCCER":
        leg["league"] = league


def _all_picks_pinned(picks: list[ParsedPick]) -> bool:
    """True only if every pick (and every parlay leg) has an event_id."""
    for pick in picks:
        if pick.pick_type == "parlay":
            legs = (pick.pick_detail or {}).get("legs", []) or []
            if not legs:
                return False
            if not all(leg.get("event_id") for leg in legs):
                return False
        elif pick.event_id is None:
            return False
    return True


def _summarize_unpinned_picks(picks: list[ParsedPick]) -> list[dict]:
    """User-facing summary of what the parser saw — used in needs_review responses."""
    summaries: list[dict] = []
    for parsed in picks:
        summaries.append({
            "sport": parsed.sport,
            "league": parsed.league,
            "event": parsed.event,
            "pick_type": parsed.pick_type,
            "pick_detail": parsed.pick_detail,
            "odds": parsed.odds,
        })
    return summaries


