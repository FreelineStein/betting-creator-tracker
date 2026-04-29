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
from datetime import datetime
from typing import Optional

import structlog

from app.config import settings
from app.pipeline.parser import ParsedPick
from app.services.espn_stats import ScheduledGame, get_scheduled_games

log = structlog.get_logger()

_MODEL = "claude-sonnet-4-6"


async def pin_unmatched_picks(
    raw_text: str,
    picks: list[ParsedPick],
    posted_at: Optional[datetime] = None,
) -> int:
    """
    Bind any pick (or parlay leg) still missing `event_id` to a scheduled
    ESPN game by asking Claude to choose from a candidate list.

    Mutates picks in place. Returns the count of picks/legs newly pinned.

    No-op when:
      - the kill-switch is off
      - no Anthropic key is configured
      - every pick is already pinned
      - we have no scheduled games to offer as candidates
    """
    if not settings.llm_pin_fallback_enabled:
        return 0
    if not settings.anthropic_api_key:
        return 0

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
        return 0

    games_by_sport: dict[str, list[ScheduledGame]] = {}
    for sport in sports_needed:
        games_by_sport[sport] = await get_scheduled_games(
            sport, anchor_date=posted_at,
        )
    if not any(games_by_sport.values()):
        return 0

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
        return 0

    valid_ids: set[str] = {
        g.game_id for games in games_by_sport.values() for g in games
    }

    prompt = _build_prompt(raw_text, picks_payload, candidates_payload)

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
    except Exception as e:
        log.warning("pin_fallback_llm_failed", error=str(e))
        return 0

    matches = data.get("matches") if isinstance(data, dict) else None
    if not isinstance(matches, list):
        return 0

    pinned = 0
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
        j = m.get("leg_index")
        if j is None:
            if pick.event_id is None:
                pick.event_id = str(eid)
                pick.event_provider = "espn"
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
                pinned += 1

    log.info(
        "pin_fallback_complete",
        attempted=unpinned_count,
        pinned=pinned,
        candidates=len(valid_ids),
    )
    return pinned


def _build_prompt(
    raw_text: str,
    picks_payload: list[dict],
    candidates_payload: dict,
) -> str:
    return f"""You are matching sports-betting picks to specific scheduled games.

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
