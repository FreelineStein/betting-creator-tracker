"""
Outcome resolver — determines if a pick won, lost, or pushed based on game scores.

Handles: spread, moneyline, over/under, props
Props are resolved via ESPN box score data. Parlays still require manual resolution.
"""
import structlog
from datetime import datetime
from typing import Optional
from app.models.pick import PickStatus
from app.services.odds_api import GameResult

log = structlog.get_logger()


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
            log.info("Parlay needs manual resolution")
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
    line_str = str(pick_detail.get("line", ""))
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


def _resolve_moneyline(pick_detail: dict, game: GameResult) -> PickStatus:
    """Did the picked team win outright?"""
    team = pick_detail.get("team", "").lower()
    if not team:
        return PickStatus.pending

    home = game.home_team.lower()
    away = game.away_team.lower()

    if team in home:
        picked_score, opp_score = game.home_score, game.away_score
    elif team in away:
        picked_score, opp_score = game.away_score, game.home_score
    else:
        log.warning("Moneyline team not found in game", team=team, home=home, away=away)
        return PickStatus.pending

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
    """Did the combined score go over or under the total?"""
    direction = pick_detail.get("direction", "").lower()
    total_str = str(pick_detail.get("total", "0"))

    if not direction:
        return PickStatus.pending

    try:
        total = float(total_str)
    except ValueError:
        log.warning("Could not parse O/U total", total=pick_detail.get("total"))
        return PickStatus.pending

    combined = game.home_score + game.away_score

    if combined == total:
        return PickStatus.push
    elif direction == "over":
        return PickStatus.won if combined > total else PickStatus.lost
    elif direction == "under":
        return PickStatus.won if combined < total else PickStatus.lost
    else:
        return PickStatus.pending
