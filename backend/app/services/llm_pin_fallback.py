"""
LLM-driven pinning fallback.

When the standard team-name lookup against ESPN's scoreboard can't pin
every parsed pick at submission, this last-resort gate asks Claude to
bind unpinned picks (and parlay legs) to specific event_ids chosen from
the candidate scheduled-games list.

The model never invents IDs: anything it returns that isn't in the
candidate set is dropped. So the worst case is "model couldn't help"
(picks remain unpinned, route to needs_review as before), not "model
hallucinated a wrong game" (which would silently corrupt records).

Controlled by `settings.llm_pin_fallback_enabled` (default True).
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import settings
from app.pipeline.parser import ParsedPick, extract_json_object
from app.services.espn_stats import ScheduledGame, get_scheduled_games

log = structlog.get_logger()

_MODEL = "claude-sonnet-4-6"


async def pin_unmatched_picks(
    raw_text: str,
    picks: list[ParsedPick],
    posted_at: Optional[datetime] = None,
) -> dict:
    """
    Bind any pick (or parlay leg) still missing `event_id` to a scheduled
    ESPN game by asking Claude to choose from a candidate list.

    Mutates picks in place. Returns a diagnostic dict:
      {
        "pinned":           int,        # legs/picks newly bound
        "attempted":        int,        # legs/picks asked about
        "candidates":       int,        # total scheduled-game options offered
        "raw_response":     str | None, # Claude's text reply (None if call failed)
        "skipped_reason":   str | None, # short tag if we returned early
      }

    Returns a no-op dict (with skipped_reason set) when:
      - the kill-switch is off
      - no Anthropic key is configured
      - every pick is already pinned
      - we have no scheduled games to offer as candidates
    """
    if not settings.llm_pin_fallback_enabled:
        return {"pinned": 0, "attempted": 0, "candidates": 0, "raw_response": None, "skipped_reason": "disabled"}
    if not settings.anthropic_api_key:
        return {"pinned": 0, "attempted": 0, "candidates": 0, "raw_response": None, "skipped_reason": "no_anthropic_key"}

    sports_needed: set[str] = set()
    unpinned_count = 0
    for pick in picks:
        if pick.pick_type == "parlay":
            for leg in (pick.pick_detail or {}).get("legs", []) or []:
                if not leg.get("event_id") and leg.get("sport"):
                    sports_needed.add(leg["sport"])
                    unpinned_count += 1
        elif pick.event_id is None and pick.sport:
            sports_needed.add(pick.sport)
            unpinned_count += 1

    if unpinned_count == 0 or not sports_needed:
        return {
            "pinned": 0,
            "attempted": 0,
            "candidates": 0,
            "raw_response": None,
            "skipped_reason": "nothing_to_pin",
        }

    games_by_sport: dict[str, list[ScheduledGame]] = {}
    for sport in sports_needed:
        games_by_sport[sport] = await get_scheduled_games(
            sport, anchor_date=posted_at,
        )
    if not any(games_by_sport.values()):
        return {
            "pinned": 0,
            "attempted": unpinned_count,
            "candidates": 0,
            "raw_response": None,
            "skipped_reason": "no_scheduled_games",
        }

    # Flat lookup so we can grab a game's commence_time from any returned event_id.
    games_by_id: dict[str, ScheduledGame] = {
        g.game_id: g
        for games in games_by_sport.values()
        for g in games
    }

    candidates_payload = {
        sport: [
            {
                "event_id": g.game_id,
                "matchup_short": f"{g.away_short} @ {g.home_short}",
                "home_team": g.home_team,
                "away_team": g.away_team,
                "commence_time": g.commence_time.isoformat(),
            }
            for g in games
        ]
        for sport, games in games_by_sport.items()
        if games
    }

    picks_payload: list[dict] = []
    for i, pick in enumerate(picks):
        if pick.pick_type == "parlay":
            legs = (pick.pick_detail or {}).get("legs", []) or []
            for j, leg in enumerate(legs):
                if leg.get("event_id"):
                    continue
                detail = leg.get("detail") or {}
                picks_payload.append({
                    "pick_index": i,
                    "leg_index": j,
                    "sport": leg.get("sport"),
                    "type": leg.get("type"),
                    "team_or_player": detail.get("team") or detail.get("player"),
                    "text": leg.get("text"),
                    "event": leg.get("event"),
                })
        elif pick.event_id is None:
            detail = pick.pick_detail or {}
            picks_payload.append({
                "pick_index": i,
                "leg_index": None,
                "sport": pick.sport,
                "type": pick.pick_type,
                "team_or_player": detail.get("team") or detail.get("player"),
                "event": pick.event,
            })

    if not picks_payload:
        return {
            "pinned": 0,
            "attempted": 0,
            "candidates": 0,
            "raw_response": None,
            "skipped_reason": "empty_payload",
        }

    valid_ids: set[str] = {
        g.game_id for games in games_by_sport.values() for g in games
    }

    prompt = _build_prompt(raw_text, picks_payload, candidates_payload, posted_at)

    raw_response: Optional[str] = None
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_response = message.content[0].text.strip()
        data = json.loads(extract_json_object(raw_response))
    except Exception as e:
        log.warning("pin_fallback_llm_failed", error=str(e))
        return {
            "pinned": 0,
            "attempted": unpinned_count,
            "candidates": len(valid_ids),
            "raw_response": raw_response,
            "skipped_reason": f"llm_error:{e}",
        }

    matches = data.get("matches") if isinstance(data, dict) else None
    if not isinstance(matches, list):
        return {
            "pinned": 0,
            "attempted": unpinned_count,
            "candidates": len(valid_ids),
            "raw_response": raw_response,
            "skipped_reason": "no_matches_in_response",
        }

    pinned = 0
    parlay_legs_pinned: dict[int, list[ScheduledGame]] = {}

    for m in matches:
        if not isinstance(m, dict):
            continue
        eid = m.get("event_id")
        if not eid or eid not in valid_ids:
            # hallucination guard: silently drop anything outside candidates
            continue
        i = m.get("pick_index")
        if not isinstance(i, int) or i < 0 or i >= len(picks):
            continue
        pick = picks[i]
        game = games_by_id.get(str(eid))
        j = m.get("leg_index")
        if j is None:
            if pick.event_id is None:
                pick.event_id = str(eid)
                pick.event_provider = "espn"
                # Mirror _pin_pick_to_game: lift the game's commence_time onto
                # event_date when we don't have one, OR when the parser's date
                # is far from the pinned game (>24h). The parser hallucinates
                # years for dates like "May 8" and the verified ESPN game is
                # ground truth once we've pinned to it.
                if game:
                    if pick.event_date is None:
                        pick.event_date = game.commence_time
                    else:
                        # Parser sometimes emits a naive date-only string;
                        # game.commence_time is always UTC-aware. Treat naive
                        # parser dates as UTC for comparison.
                        parser_aware = (
                            pick.event_date
                            if pick.event_date.tzinfo
                            else pick.event_date.replace(tzinfo=timezone.utc)
                        )
                        if abs((parser_aware - game.commence_time).total_seconds()) > 24 * 3600:
                            pick.event_date = game.commence_time
                pinned += 1
        else:
            if not isinstance(j, int) or j < 0:
                continue
            legs = (pick.pick_detail or {}).get("legs", []) or []
            if j >= len(legs):
                continue
            leg = legs[j]
            if not leg.get("event_id"):
                leg["event_id"] = str(eid)
                leg["event_provider"] = "espn"
                if game:
                    parlay_legs_pinned.setdefault(i, []).append(game)
                pinned += 1

    # For parlays where we just pinned legs, set the parent pick's event_date
    # to the earliest leg commence_time if it's not already set. The homepage
    # groups picks by date — without this, multi-game parlays display "Today"
    # even when all their legs were on a specific past date.
    for i, leg_games in parlay_legs_pinned.items():
        pick = picks[i]
        if not leg_games:
            continue
        earliest = min(g.commence_time for g in leg_games)
        if pick.event_date is None:
            pick.event_date = earliest
        else:
            parser_aware = (
                pick.event_date
                if pick.event_date.tzinfo
                else pick.event_date.replace(tzinfo=timezone.utc)
            )
            if abs((parser_aware - earliest).total_seconds()) > 24 * 3600:
                pick.event_date = earliest

    log.info(
        "pin_fallback_complete",
        attempted=unpinned_count,
        pinned=pinned,
        candidates=len(valid_ids),
    )
    return {
        "pinned": pinned,
        "attempted": unpinned_count,
        "candidates": len(valid_ids),
        "raw_response": raw_response,
        "skipped_reason": None,
    }


def _build_prompt(
    raw_text: str,
    picks_payload: list[dict],
    candidates_payload: dict,
    posted_at: Optional[datetime] = None,
) -> str:
    # When two candidate games involve the same teams on consecutive days
    # (common in MLB/NHL series), the LLM has no way to disambiguate
    # without knowing when the user actually wrote the post. The tweet's
    # posted_at is the tight anchor — "today's picks" almost always means
    # the calendar day in ET that the tweet was posted, never one earlier.
    when_line = ""
    if posted_at:
        anchor = posted_at if posted_at.tzinfo else posted_at.replace(tzinfo=timezone.utc)
        when_line = (
            f'\nThe post was published at {anchor.isoformat()} UTC. When the post says "today" '
            f'or doesn\'t name a date, prefer candidate games whose commence_time falls on the '
            f'same day or the next day after posting (in US Eastern time). Reject candidates '
            f'whose commence_time is earlier than the post — a creator doesn\'t pre-tweet a pick '
            f'for a game that has already happened.\n'
        )

    return f"""You are matching sports-betting picks to specific scheduled games.
{when_line}

Below is the original creator post, a list of picks (or parlay legs) that
the parser couldn't auto-bind to a game, and a list of candidate scheduled
games per sport. For each unbound pick, choose the matching `event_id`
from the candidates.

Posts routinely use 3-letter abbreviations (BOS, TOR, LAA, NYY, CHC, SD,
MIA, LAD, etc.), city names, nicknames ("Cavs", "Sixers"), or player names
without their team. These reliably correspond to specific franchises —
BOS → Boston Red Sox, TOR → Toronto Blue Jays, LAA → Los Angeles Angels,
LAD → Los Angeles Dodgers, NYY → New York Yankees, MIA → Miami Marlins,
SD/SDP → San Diego Padres, CHC → Chicago Cubs, CWS/CHW → Chicago White Sox,
TEX → Texas Rangers, etc. Make the connection — that's the point of this
step. The standard string-matcher already failed on these and you are
its fallback.

Return null only when the post is genuinely ambiguous (no usable team,
no player, no time hint that distinguishes between multiple candidate
games). Player props are usually disambiguated by the player's team:
e.g., "Aaron Judge HR" maps to NYY's game on the relevant date.

CRITICAL: only return event_ids that appear in the candidates list — never
invent or guess IDs.

Original post:
\"\"\"
{raw_text[:4000]}
\"\"\"

Unbound picks (and parlay legs):
{json.dumps(picks_payload, indent=2)}

Candidate scheduled games by sport (each candidate carries event_id,
short matchup, full home_team and away_team, and commence_time):
{json.dumps(candidates_payload, indent=2)}

Respond with a single JSON object — no prose, no markdown fences:
{{
  "matches": [
    {{"pick_index": <int>, "leg_index": <int|null>, "event_id": "<string from candidates, or null>"}}
  ]
}}

Include one entry per unbound pick. Use leg_index for parlay legs, null for top-level picks.
"""
