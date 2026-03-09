"""
The Odds API client — fetches completed game scores for outcome resolution.
Docs: https://the-odds-api.com/liveapi/guides/v4/

Free tier: 500 requests/month. We only call this for sports that have pending picks,
so real-world usage will be well under the limit.
"""
import httpx
import structlog
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional

from app.config import settings

log = structlog.get_logger()

BASE_URL = "https://api.the-odds-api.com/v4"

# Map our sport abbreviations to The Odds API sport keys
SPORT_KEY_MAP = {
    "NFL":   "americanfootball_nfl",
    "CFB":   "americanfootball_ncaaf",
    "NBA":   "basketball_nba",
    "CBB":   "basketball_ncaab",
    "NCAAB": "basketball_ncaab",
    "MLB":   "baseball_mlb",
    "NHL":   "icehockey_nhl",
    "MLS":   "soccer_usa_mls",
    "WNBA":  "basketball_wnba",
}


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
    days_back: how many days of history to fetch (free tier supports up to 3 days)
    """
    sport_key = SPORT_KEY_MAP.get(sport.upper())
    if not sport_key:
        log.warning("No Odds API key mapping for sport", sport=sport)
        return []

    if not settings.the_odds_api_key:
        log.warning("THE_ODDS_API_KEY not configured — skipping outcome resolution")
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
    Fuzzy-match a pick's event string to a completed game.
    Checks if team names from the pick appear in the game's home/away teams.
    """
    if not games:
        return None

    # Extract team name candidates from the pick
    team_candidates = set()

    if team := pick_detail.get("team"):
        team_candidates.add(team.lower())

    if event:
        # "Chiefs vs Raiders" → ["Chiefs", "Raiders"]
        for part in event.replace(" vs ", " ").replace(" @ ", " ").split():
            if len(part) > 3:
                team_candidates.add(part.lower())

    for game in games:
        home = game.home_team.lower()
        away = game.away_team.lower()

        # Check if any candidate team name appears in home or away team names
        for candidate in team_candidates:
            if candidate in home or candidate in away:
                # If we have a date, sanity check it's within 24h
                if event_date:
                    diff = abs((game.commence_time - event_date).total_seconds())
                    if diff > 86400:  # More than 24h apart
                        continue
                return game

    return None
