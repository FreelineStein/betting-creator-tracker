"""
The Odds API client — fetches completed game scores for outcome resolution.
Docs: https://the-odds-api.com/liveapi/guides/v4/

Free tier: 500 requests/month. Budget is tracked via odds_api_budget.py.
Results are cached for 30 minutes to avoid redundant calls.
"""
import httpx
import structlog
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.services.odds_api_budget import check_budget, record_request

log = structlog.get_logger()

BASE_URL = "https://api.the-odds-api.com/v4"

# Map our sport abbreviations to The Odds API sport keys
SPORT_KEY_MAP = {
    "NFL":   "americanfootball_nfl",
    "CFB":   "americanfootball_ncaaf",
    "NCAAF": "americanfootball_ncaaf",
    "NBA":   "basketball_nba",
    "CBB":   "basketball_ncaab",
    "NCAAB": "basketball_ncaab",
    "MLB":   "baseball_mlb",
    "NHL":   "icehockey_nhl",
    "MLS":   "soccer_usa_mls",
    "WNBA":  "basketball_wnba",
    "WBC":   "baseball_wbc",
}

# Simple in-memory cache: {sport_key: (timestamp, results)}
_cache: dict[str, tuple[datetime, list]] = {}
CACHE_TTL = timedelta(minutes=30)


@dataclass
class GameResult:
    game_id: str
    sport: str
    home_team: str
    away_team: str
    home_score: Optional[int]
    away_score: Optional[int]
    completed: bool
    commence_time: datetime


async def get_completed_games(sport: str, days_back: int = 3) -> list[GameResult]:
    """
    Fetch recently completed games for a sport.
    Uses cache to avoid burning through the free tier budget.
    """
    sport_key = SPORT_KEY_MAP.get(sport.upper())
    if not sport_key:
        log.warning("No Odds API key mapping for sport", sport=sport)
        return []

    if not settings.the_odds_api_key:
        log.warning("THE_ODDS_API_KEY not configured — skipping outcome resolution")
        return []

    # Check cache first
    now = datetime.now(timezone.utc)
    if sport_key in _cache:
        cached_at, cached_results = _cache[sport_key]
        if now - cached_at < CACHE_TTL:
            log.info("Using cached game results", sport=sport, count=len(cached_results))
            return cached_results

    # Check budget before making a request
    if not check_budget():
        return []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/sports/{sport_key}/scores",
                params={
                    "apiKey": settings.the_odds_api_key,
                    "daysFrom": days_back,
                },
            )
            resp.raise_for_status()
            games_data = resp.json()

        record_request()

        results = []
        for game in games_data:
            if not game.get("completed"):
                continue

            home_score = away_score = None
            for score in game.get("scores") or []:
                if score["name"] == game["home_team"]:
                    home_score = int(score["score"])
                elif score["name"] == game["away_team"]:
                    away_score = int(score["score"])

            results.append(GameResult(
                game_id=game["id"],
                sport=sport,
                home_team=game["home_team"],
                away_team=game["away_team"],
                home_score=home_score,
                away_score=away_score,
                completed=True,
                commence_time=datetime.fromisoformat(
                    game["commence_time"].replace("Z", "+00:00")
                ),
            ))

        # Cache results
        _cache[sport_key] = (now, results)

        log.info("Fetched completed games", sport=sport, count=len(results))
        return results

    except Exception as e:
        log.error("Odds API request failed", sport=sport, error=str(e))
        return []


def find_matching_game(
    event: str,
    pick_detail: dict,
    event_date: Optional[datetime],
    games: list[GameResult],
) -> Optional[GameResult]:
    """
    Match a pick's event string to a completed game.
    Uses team name matching with date filtering.
    """
    if not games:
        return None

    # Extract team name from pick detail
    pick_team = (pick_detail.get("team") or "").lower().strip()

    # Extract team names from event string ("Chiefs vs Raiders")
    event_teams = set()
    if event:
        for part in event.replace(" vs ", "|").replace(" @ ", "|").replace(" vs. ", "|").split("|"):
            cleaned = part.strip().lower()
            if cleaned:
                event_teams.add(cleaned)

    # Filter games by date first (±24h)
    date_filtered = games
    if event_date:
        date_filtered = [
            g for g in games
            if abs((g.commence_time - event_date).total_seconds()) <= 86400
        ]

    matches = []
    for game in date_filtered:
        home = game.home_team.lower()
        away = game.away_team.lower()

        # Try exact match on full team name first
        if pick_team and (pick_team == home or pick_team == away):
            return game

        # Try if pick team is contained in full team name (e.g., "Chiefs" in "Kansas City Chiefs")
        if pick_team and (pick_team in home or pick_team in away):
            matches.append(game)
            continue

        # Try matching event teams
        for et in event_teams:
            if et in home or et in away or home in et or away in et:
                matches.append(game)
                break

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        log.warning(
            "Ambiguous game match — multiple games matched, marking for review",
            event=event,
            pick_team=pick_team,
            match_count=len(matches),
        )
        return None

    return None
