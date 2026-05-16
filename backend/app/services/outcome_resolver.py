"""
Outcome resolver — determines if a pick won, lost, or pushed based on game scores.

Handles: spread, moneyline, over/under, props, parlays (per-leg resolution)
"""
import structlog
from datetime import datetime
from typing import Optional
from app.models.pick import PickStatus
from app.services.odds_api import GameResult
from app.services.espn_stats import ScheduledGame

log = structlog.get_logger()


# Props phrased as a "did it happen" yes/no — books default the line to 0.5
# (Over 0.5 = at least 1). When the parser doesn't pick up an explicit line
# (e.g., "Aaron Judge HR" with no number), fall back to 0.5 + Over so we can
# still settle the pick instead of leaving it pending forever.
_BINARY_PROPS_LOWER = {
    "home run", "home runs", "hr",
    "touchdown", "touchdowns", "td",
    "goal", "goals",
    "stolen base", "sb",
}


def _resolve_default_prop_line(prop: str, line: Optional[str]) -> Optional[str]:
    """Default line=0.5 for known binary props when the parser didn't capture one."""
    if line not in (None, ""):
        return line
    if not prop:
        return None
    return "0.5" if prop.strip().lower() in _BINARY_PROPS_LOWER else None


def scheduled_to_game_result(sg: ScheduledGame) -> GameResult:
    """
    Convert an ESPN ScheduledGame into a GameResult so the existing
    resolve_pick / find_matching_game pipeline can consume it without
    knowing the source. Used by the ESPN-first resolution path.
    """
    return GameResult(
        game_id=sg.game_id,
        sport=sg.sport,
        home_team=sg.home_team,
        away_team=sg.away_team,
        home_score=sg.home_score,
        away_score=sg.away_score,
        completed=sg.completed,
        commence_time=sg.commence_time,
        home_short=sg.home_short,
        away_short=sg.away_short,
        winner_side=sg.winner_side,
    )


def resolve_pick(
    pick_type: str,
    pick_detail: dict,
    game: Optional[GameResult] = None,
) -> PickStatus:
    """
    Given a pick and its game result, return the outcome.
    Returns PickStatus.pending if resolution is not possible.
    For props, game can be None (resolved via ESPN stats separately).
    """
    if pick_type == "prop":
        # Props are resolved via resolve_prop() — not through game scores
        return PickStatus.pending

    if game is None or not game.completed:
        return PickStatus.pending

    if game.home_score is None or game.away_score is None:
        return PickStatus.pending

    try:
        if pick_type == "moneyline":
            return _resolve_moneyline(pick_detail, game)
        elif pick_type == "spread":
            return _resolve_spread(pick_detail, game)
        elif pick_type == "over_under":
            return _resolve_over_under(pick_detail, game)
        elif pick_type == "parlay":
            # Parlays are resolved per-leg via resolve_parlay_legs()
            return PickStatus.pending
        else:
            return PickStatus.pending
    except Exception as e:
        log.warning("Resolution failed", pick_type=pick_type, error=str(e))
        return PickStatus.pending


async def resolve_prop(
    pick_detail: dict,
    sport: str,
    event_date: Optional[datetime] = None,
) -> PickStatus:
    """
    Resolve a player prop bet using ESPN box score data.
    Returns won/lost/push/pending.
    """
    from app.services.espn_stats import find_player_stat

    player = pick_detail.get("player", "")
    prop = pick_detail.get("prop", "")
    raw_line = pick_detail.get("line")
    line_str = str(raw_line) if raw_line not in (None, "") else ""
    if not line_str:
        defaulted = _resolve_default_prop_line(prop, line_str or None)
        if defaulted:
            line_str = defaulted
    direction = pick_detail.get("direction", "over").lower()

    if not player or not prop or not line_str:
        log.warning("Incomplete prop pick detail", pick_detail=pick_detail)
        return PickStatus.pending

    try:
        line = float(line_str)
    except ValueError:
        log.warning("Could not parse prop line", line=line_str)
        return PickStatus.pending

    result = await find_player_stat(player, prop, sport, event_date)
    if result is None:
        log.info("Could not find player stat for prop", player=player, prop=prop, sport=sport)
        return PickStatus.pending

    log.info(
        "Prop stat found",
        player=result.player_name,
        prop=prop,
        actual=result.stat_value,
        line=line,
        direction=direction,
    )

    if result.stat_value == line:
        return PickStatus.push
    elif direction == "over":
        return PickStatus.won if result.stat_value > line else PickStatus.lost
    elif direction == "under":
        return PickStatus.won if result.stat_value < line else PickStatus.lost
    else:
        return PickStatus.pending


def _team_side(team: str, game: GameResult) -> Optional[str]:
    """Return 'home' or 'away' if `team` matches either side of `game`.

    Checks both the full displayName and the short form (when available)
    so a pick stored as the short name ("Man City") still resolves against
    a game whose home_team is the longer displayName ("Manchester City").
    """
    from app.services.espn_stats import team_matches

    candidates_home = [game.home_team] + ([game.home_short] if game.home_short else [])
    candidates_away = [game.away_team] + ([game.away_short] if game.away_short else [])
    if any(team_matches(team, c) for c in candidates_home if c):
        return "home"
    if any(team_matches(team, c) for c in candidates_away if c):
        return "away"
    return None


def _resolve_moneyline(pick_detail: dict, game: GameResult) -> PickStatus:
    """Did the picked team (or tennis player) win outright?"""
    # Tennis picks carry the competitor in `player` rather than `team`.
    team = (pick_detail.get("team") or pick_detail.get("player") or "").strip()
    if not team:
        return PickStatus.pending

    picked_side = _team_side(team, game)
    if not picked_side:
        log.warning(
            "Moneyline team not found in game",
            team=team, home=game.home_team, away=game.away_team,
        )
        return PickStatus.pending

    # Cup-final "to lift the cup" markets settle on the full match outcome
    # (regulation + extra time + penalty shootout). Trust ESPN's winner_side
    # over a raw score compare so a PK-decided draw resolves correctly.
    if pick_detail.get("includes_extra_time") and game.winner_side:
        return PickStatus.won if picked_side == game.winner_side else PickStatus.lost

    picked_score, opp_score = (
        (game.home_score, game.away_score)
        if picked_side == "home"
        else (game.away_score, game.home_score)
    )

    if picked_score > opp_score:
        return PickStatus.won
    elif picked_score < opp_score:
        return PickStatus.lost
    else:
        return PickStatus.push


def _resolve_spread(pick_detail: dict, game: GameResult) -> PickStatus:
    """Did the picked team cover the spread?"""
    team = pick_detail.get("team", "").lower()
    line_str = str(pick_detail.get("line", "0")).replace("+", "")

    if not team:
        return PickStatus.pending

    try:
        line = float(line_str)
    except ValueError:
        log.warning("Could not parse spread line", line=pick_detail.get("line"))
        return PickStatus.pending

    home = game.home_team.lower()
    away = game.away_team.lower()

    if team in home:
        picked_score, opp_score = game.home_score, game.away_score
    elif team in away:
        picked_score, opp_score = game.away_score, game.home_score
    else:
        log.warning("Spread team not found in game", team=team, home=home, away=away)
        return PickStatus.pending

    # Apply the line: negative = favorite (must win by more than |line|)
    # positive = underdog (can lose by less than line and still cover)
    margin = picked_score - opp_score  # positive = picked team won
    covered = margin + line  # If > 0, covered. If < 0, didn't cover. If == 0, push.

    if covered > 0:
        return PickStatus.won
    elif covered < 0:
        return PickStatus.lost
    else:
        return PickStatus.push


def _resolve_over_under(pick_detail: dict, game: GameResult) -> PickStatus:
    """
    Did the score go over or under the total?

    Two flavors:
      - Game total (no `team` in detail): combined home + away vs total.
      - Team total (detail.team set): just that one team's score vs total.
        Standard soccer market — "Aston Villa Team Total Goals Over 0.5"
        wants Villa's score alone, not the matchup total.
    """
    from app.services.espn_stats import team_matches

    direction = pick_detail.get("direction", "").lower()
    total_str = str(pick_detail.get("total", "0"))

    if not direction:
        return PickStatus.pending

    try:
        total = float(total_str)
    except ValueError:
        log.warning("Could not parse O/U total", total=pick_detail.get("total"))
        return PickStatus.pending

    team = (pick_detail.get("team") or "").strip()
    team_side = (pick_detail.get("team_side") or "").strip().lower()
    if team_side in ("home", "away"):
        # "Away Team Over/Under N" / "Home Team Over/Under N" markets — the
        # parser couldn't reliably guess which named team was the away side,
        # so it deferred the home/away assignment to here, where ESPN's
        # competitors[].homeAway flag is the source of truth.
        value = game.home_score if team_side == "home" else game.away_score
    elif team:
        if team_matches(team, game.home_team):
            value = game.home_score
        elif team_matches(team, game.away_team):
            value = game.away_score
        else:
            log.warning(
                "Team-total team not found in game",
                team=team, home=game.home_team, away=game.away_team,
            )
            return PickStatus.pending
    else:
        value = game.home_score + game.away_score

    if value == total:
        return PickStatus.push
    elif direction == "over":
        return PickStatus.won if value > total else PickStatus.lost
    elif direction == "under":
        return PickStatus.won if value < total else PickStatus.lost
    else:
        return PickStatus.pending


_FIRST_INNING_KEYWORDS = (
    "nrfi", "yrfi", "no run first inning", "yes run first inning",
    "no runs first inning", "yes runs first inning",
)


def _is_first_inning_runs_prop(prop_name: str) -> bool:
    """True if `prop_name` describes the combined first-inning runs market."""
    if not prop_name:
        return False
    needle = prop_name.lower()
    return any(k in needle for k in _FIRST_INNING_KEYWORDS)


async def _resolve_first_inning_runs(
    pick_detail: dict, event_id: str,
) -> PickStatus:
    """
    Resolve an NRFI / YRFI prop against ESPN's MLB linescore for the
    pinned game.

    The detail looks like `{prop: "No Run First Inning", direction: "Yes"}`
    (or "Yes Run First Inning" / direction "No"). We collapse the
    (prop, direction) pair to a single "user expects 0 runs?" flag, then
    compare against the sum of both teams' first-inning runs.
    """
    from app.services.espn_stats import get_first_inning_runs

    prop_name = (pick_detail.get("prop") or "").lower()
    direction = (pick_detail.get("direction") or "").lower()

    is_nrfi = "no run" in prop_name or "nrfi" in prop_name
    is_yrfi = "yes run" in prop_name or "yrfi" in prop_name
    if not (is_nrfi or is_yrfi):
        return PickStatus.pending

    # Direction "Yes" means the user took the market name as written:
    # NRFI Yes → expects no runs; YRFI Yes → expects runs.
    direction_yes = direction in ("yes", "y", "true", "over")
    user_expects_no_runs = is_nrfi == direction_yes

    runs = await get_first_inning_runs(event_id)
    if runs is None:
        log.info("first_inning_runs not available", event_id=event_id)
        return PickStatus.pending

    log.info(
        "first_inning_runs resolved",
        event_id=event_id, runs=runs,
        prop=pick_detail.get("prop"), direction=pick_detail.get("direction"),
        user_expects_no_runs=user_expects_no_runs,
    )

    if runs == 0:
        return PickStatus.won if user_expects_no_runs else PickStatus.lost
    return PickStatus.lost if user_expects_no_runs else PickStatus.won


_BTTS_KEYWORDS = (
    "both teams to score",
    "btts",
)


def _is_btts_prop(prop_name: str) -> bool:
    """True if `prop_name` describes the Both Teams To Score market."""
    if not prop_name:
        return False
    needle = prop_name.lower()
    return any(k in needle for k in _BTTS_KEYWORDS)


async def _resolve_btts(
    pick_detail: dict, event_id: str, anchor_date: Optional[datetime] = None,
) -> PickStatus:
    """
    Resolve a Both-Teams-To-Score soccer prop against the pinned match's
    final scoreline. detail.direction follows the binary-prop convention:
    Over 0.5 = "Yes BTTS", Under 0.5 = "No BTTS". Cup-final variants that
    include extra time are still fine because ESPN's competitors[].score
    is the regulation + extra-time aggregate (PK shootout goals are not
    counted toward BTTS by sportsbook convention either).
    """
    from app.services.espn_stats import find_completed_game_by_event_id

    direction = (pick_detail.get("direction") or "").strip().lower()
    if direction not in ("over", "under"):
        return PickStatus.pending

    sched = await find_completed_game_by_event_id(
        "SOCCER", event_id, anchor_date=anchor_date,
    )
    if not sched or not sched.completed:
        return PickStatus.pending
    if sched.home_score is None or sched.away_score is None:
        return PickStatus.pending

    both_scored = sched.home_score > 0 and sched.away_score > 0
    log.info(
        "btts resolved",
        event_id=event_id, home=sched.home_score, away=sched.away_score,
        direction=direction, both_scored=both_scored,
    )
    if direction == "over":
        return PickStatus.won if both_scored else PickStatus.lost
    return PickStatus.lost if both_scored else PickStatus.won


async def _resolve_first_half_total(
    pick_detail: dict,
    event_id: str,
    league_display: Optional[str] = None,
) -> PickStatus:
    """
    Resolve a 1H (first-half) game-total over/under for a soccer match.

    pick_detail looks like `{direction: "Over"|"Under", total: "1.5", period: "1H"}`.
    Reads ESPN's summary endpoint for the pinned event and sums both teams'
    first-half goals from competitors[].linescores[0]. Game-total only — a
    team-total 1H pick (e.g. "Bayern 1H Goals Over 0.5") would need its own
    handler since we'd need per-team linescores, not the combined total.
    """
    from app.services.espn_stats import get_soccer_first_half_total

    direction = (pick_detail.get("direction") or "").strip().lower()
    total_str = str(pick_detail.get("total") or "")
    if direction not in ("over", "under") or not total_str:
        return PickStatus.pending
    try:
        total = float(total_str)
    except ValueError:
        return PickStatus.pending

    runs = await get_soccer_first_half_total(event_id, league_display=league_display)
    if runs is None:
        return PickStatus.pending

    log.info(
        "first_half_total resolved",
        event_id=event_id, total=total, direction=direction, actual=runs,
    )
    if runs == total:
        return PickStatus.push
    if direction == "over":
        return PickStatus.won if runs > total else PickStatus.lost
    return PickStatus.won if runs < total else PickStatus.lost


async def resolve_prop_pinned(
    pick_detail: dict,
    sport: str,
    event_id: str,
    event_date: Optional[datetime] = None,
) -> PickStatus:
    """
    Resolve a player prop against the box score of a specific ESPN event_id.

    Mirrors resolve_prop's contract but starts from the pinned event_id
    instead of searching by date. If the player isn't in the pinned game's
    box score — i.e. the LLM pinned to the wrong game (closest-game
    fallback chose Mets@Nationals instead of the player's actual team's
    game) — and `event_date` is available, falls back to find_player_stat
    for a wider ±1 day search across that day's slate. That catches
    misclassified pins without needing a player→team mapping.
    """
    # Game-level special-period markets (NRFI / YRFI) don't have a player
    # and aren't in find_player_stat — they read the linescore directly.
    if _is_first_inning_runs_prop(pick_detail.get("prop", "")):
        return await _resolve_first_inning_runs(pick_detail, event_id)

    # Soccer Both-Teams-To-Score has no player — settles from the final
    # match scoreline, same shape as the binary "Yes/No" prop.
    if _is_btts_prop(pick_detail.get("prop", "")):
        return await _resolve_btts(pick_detail, event_id, anchor_date=event_date)

    from app.services.espn_stats import (
        find_player_stat_in_event, find_player_stat,
        find_soccer_player_stat_in_event,
    )

    player = pick_detail.get("player", "")
    prop = pick_detail.get("prop", "")
    raw_line = pick_detail.get("line")
    line_str = str(raw_line) if raw_line not in (None, "") else ""
    if not line_str:
        defaulted = _resolve_default_prop_line(prop, line_str or None)
        if defaulted:
            line_str = defaulted
    direction = pick_detail.get("direction", "over").lower()

    if not player or not prop or not line_str:
        log.warning("Incomplete prop pick detail", pick_detail=pick_detail)
        return PickStatus.pending

    try:
        line = float(line_str)
    except ValueError:
        log.warning("Could not parse prop line", line=line_str)
        return PickStatus.pending

    # Soccer player props read different stat keys and live in a different
    # ESPN structure (summary.rosters[].roster[].stats[]) than the
    # team-sport box scores — route them through the soccer-specific lookup.
    if sport and sport.upper() == "SOCCER":
        result = await find_soccer_player_stat_in_event(event_id, player, prop)
    else:
        result = await find_player_stat_in_event(sport, event_id, player, prop)
    if result is None and event_date is not None and (not sport or sport.upper() != "SOCCER"):
        # Pinned-game miss — try the wider day-window search in case the
        # LLM pinned to the wrong game (player isn't on either team there).
        # Skipped for soccer because find_player_stat doesn't know how to
        # walk soccer summary rosters; the pinned soccer lookup is final.
        result = await find_player_stat(player, prop, sport, event_date)
        if result is not None:
            log.info(
                "Pinned prop rescued via day-window search",
                player=player, prop=prop, sport=sport,
                pinned_event_id=event_id,
            )
    if result is None:
        log.info(
            "Pinned prop stat not found",
            player=player, prop=prop, sport=sport, event_id=event_id,
        )
        return PickStatus.pending

    log.info(
        "Pinned prop stat found",
        player=result.player_name, prop=prop,
        actual=result.stat_value, line=line, direction=direction,
    )

    if result.stat_value == line:
        return PickStatus.push
    elif direction == "over":
        return PickStatus.won if result.stat_value > line else PickStatus.lost
    elif direction == "under":
        return PickStatus.won if result.stat_value < line else PickStatus.lost
    return PickStatus.pending


async def resolve_parlay_legs_pinned(
    pick_detail: dict,
    anchor_date: Optional[datetime] = None,
) -> tuple[dict, PickStatus]:
    """
    Resolve each parlay leg via its own pinned `event_id`.

    Each leg in `pick_detail.legs` carries its own `event_id` (set at
    submission via `_pin_leg_to_game`), so we can look up the exact game
    or box score per leg without any fuzzy matching. Legs missing
    `event_id` are skipped (left pending) — they should be rare and only
    occur on legacy data.

    `anchor_date` controls the ESPN scoreboard window used for the
    leg's game lookup. Without it, the lookup defaults to "now",
    which excludes parlays whose games are more than ~1 day in the past
    (the scoreboard window is anchor−1 to anchor+5). Callers should
    pass the parent pick's `event_date` so legs on or near that date
    fall inside the window.

    Returns (updated pick_detail with per-leg results, overall parlay status).
    """
    from app.services.espn_stats import find_completed_game_by_event_id

    legs = pick_detail.get("legs", [])
    if not legs:
        return pick_detail, PickStatus.pending

    for leg in legs:
        if not isinstance(leg, dict):
            continue
        if leg.get("result") in ("won", "lost", "push"):
            continue

        leg_event_id = leg.get("event_id")
        leg_sport = leg.get("sport", "")
        leg_type = leg.get("type", "")
        leg_detail = leg.get("detail", {})

        if not leg_event_id or not leg_sport or not leg_type or not leg_detail:
            continue

        if leg_type == "prop":
            result = await resolve_prop_pinned(
                leg_detail, leg_sport, leg_event_id, event_date=anchor_date,
            )
        elif (
            leg_type == "over_under"
            and (leg_detail.get("period") or "").upper() == "1H"
            and leg_sport.upper() == "SOCCER"
            and not leg_detail.get("team")  # game-total only for now
            and not leg_detail.get("team_side")
        ):
            result = await _resolve_first_half_total(
                leg_detail, leg_event_id, league_display=leg.get("league"),
            )
        else:
            game_sched = await find_completed_game_by_event_id(
                leg_sport, leg_event_id, anchor_date=anchor_date,
            )
            if not game_sched or not game_sched.completed:
                continue
            game = scheduled_to_game_result(game_sched)
            result = resolve_pick(leg_type, leg_detail, game)

        if result != PickStatus.pending:
            leg["result"] = result.value
            log.info(
                "Parlay leg resolved (pinned)",
                text=leg.get("text"), result=result.value, event_id=leg_event_id,
            )

    overall = _parlay_status_from_legs(legs)
    return pick_detail, overall


async def resolve_parlay_legs(
    pick_detail: dict,
    event_date: Optional[datetime] = None,
) -> tuple[dict, PickStatus]:
    """
    Resolve each leg of a parlay individually.
    Returns (updated pick_detail with per-leg results, overall parlay status).
    Overall: all won → won, any lost → lost, all resolved but some push → won (push legs don't kill parlays),
    any still pending → pending.
    """
    from app.services.odds_api import get_completed_games, find_matching_game, SPORT_KEY_MAP

    legs = pick_detail.get("legs", [])
    if not legs:
        return pick_detail, PickStatus.pending

    # Cache games by sport to minimize API calls
    games_cache: dict[str, list] = {}
    any_updated = False

    for leg in legs:
        if not isinstance(leg, dict):
            continue
        if leg.get("result") in ("won", "lost", "push"):
            continue  # Already resolved

        leg_type = leg.get("type", "")
        leg_detail = leg.get("detail", {})
        leg_sport = leg.get("sport", "")

        if not leg_type or not leg_detail:
            continue

        # Resolve props via ESPN
        if leg_type == "prop":
            if leg_sport:
                result = await resolve_prop(leg_detail, leg_sport, event_date)
                if result != PickStatus.pending:
                    leg["result"] = result.value
                    any_updated = True
                    log.info("Parlay leg resolved (prop)", text=leg.get("text"), result=result.value)
            continue

        # Resolve spread/ML/O-U via Odds API
        if not leg_sport or leg_sport not in SPORT_KEY_MAP:
            continue

        if leg_sport not in games_cache:
            games_cache[leg_sport] = await get_completed_games(leg_sport, days_back=3)

        games = games_cache[leg_sport]
        if not games:
            continue

        game = find_matching_game(
            event=leg.get("event", ""),
            pick_detail=leg_detail,
            event_date=event_date,
            games=games,
        )

        if not game:
            continue

        result = resolve_pick(leg_type, leg_detail, game)
        if result != PickStatus.pending:
            leg["result"] = result.value
            any_updated = True
            log.info("Parlay leg resolved", text=leg.get("text"), result=result.value)

    # Determine overall parlay status from legs
    overall = _parlay_status_from_legs(legs)

    return pick_detail, overall


def _parlay_status_from_legs(legs: list[dict]) -> PickStatus:
    """Determine overall parlay outcome from individual leg results."""
    results = [leg.get("result", "pending") for leg in legs if isinstance(leg, dict)]
    if not results:
        return PickStatus.pending

    if any(r == "lost" for r in results):
        return PickStatus.lost
    if all(r in ("won", "push") for r in results):
        return PickStatus.won
    # Some still pending
    return PickStatus.pending


def parlay_all_legs_unresolvable(legs: list) -> bool:
    """
    True if every parlay leg has detail with no actionable fields — the
    signature of a parser failure preserved on the row (e.g. an SGP from
    a bet-slip screenshot where OCR couldn't read the legs). These
    parlays can never resolve no matter how often the resolver runs,
    because there's no market data to evaluate against.

    The caller should mark the pick as `void` so it falls out of the
    pending bucket instead of sitting there indefinitely.
    """
    has_real_leg = False
    for leg in legs:
        if not isinstance(leg, dict):
            continue
        has_real_leg = True
        detail = leg.get("detail")
        if not isinstance(detail, dict):
            return False  # unexpected shape — don't void, leave for triage
        if any(v not in (None, "") for v in detail.values()):
            return False  # at least one leg carries actionable data
    return has_real_leg
