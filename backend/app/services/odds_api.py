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
from app.services.espn_stats import team_matches
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
_odds_cache: dict[str, tuple[datetime, list]] = {}
CACHE_TTL = timedelta(minutes=30)
ODDS_CACHE_TTL = timedelta(hours=6)  # lines move during the day, but for a tracker the morning snapshot is fine

# Bookmaker preference for the odds returned by /sports/{key}/odds. We pick the
# first one available in this order so the displayed price stays consistent
# across submissions. "Any other book" is the final fallback.
_BOOKMAKER_PRIORITY = ("draftkings", "fanduel", "betmgm", "caesars")


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


async def get_odds_for_sport(sport: str) -> list[dict]:
    """
    Fetch upcoming games + bookmaker prices for a sport. Used to fill in the
    `odds` field on picks where the LLM didn't extract a price from the post.

    Hits /sports/{key}/odds?regions=us&markets=h2h,spreads,totals — one
    request returns every upcoming game with all three markets. Cached for
    six hours per sport, gated by the same monthly budget guard as the
    completed-scores call.

    Returns the raw API payload (a list of dicts) — callers walk it via
    find_odds_for_pick(...) below.
    """
    sport_key = SPORT_KEY_MAP.get(sport.upper())
    if not sport_key:
        return []
    if not settings.the_odds_api_key:
        log.warning("THE_ODDS_API_KEY not configured — skipping odds enrichment")
        return []

    now = datetime.now(timezone.utc)
    if sport_key in _odds_cache:
        cached_at, cached = _odds_cache[sport_key]
        if now - cached_at < ODDS_CACHE_TTL:
            return cached

    if not check_budget():
        return []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/sports/{sport_key}/odds",
                params={
                    "apiKey": settings.the_odds_api_key,
                    "regions": "us",
                    "markets": "h2h,spreads,totals",
                    "oddsFormat": "american",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        record_request()
    except Exception as e:
        log.error("Odds API odds request failed", sport=sport, error=str(e))
        return []

    _odds_cache[sport_key] = (now, data)
    log.info("Fetched odds slate", sport=sport, count=len(data))
    return data


def _format_american(price: int) -> str:
    return f"+{price}" if price > 0 else str(price)


def _pick_bookmaker(game: dict) -> Optional[dict]:
    bookmakers = game.get("bookmakers") or []
    if not bookmakers:
        return None
    by_key = {b.get("key"): b for b in bookmakers}
    for preferred in _BOOKMAKER_PRIORITY:
        if preferred in by_key:
            return by_key[preferred]
    return bookmakers[0]


def _team_matches(team: str, candidate: str) -> bool:
    """
    Loose team-name match shared with ESPN scoreboard lookups via
    espn_stats.team_matches. Now alias-aware so "Sixers" / "Cavs" / "Avs"
    resolve to their canonical Odds API team names.
    """
    return team_matches(team, candidate)


def _find_game_for_team(team: str, games: list[dict]) -> Optional[dict]:
    """Return the soonest game where `team` is one of the participants."""
    matches = [
        g for g in games
        if _team_matches(team, g.get("home_team") or "")
        or _team_matches(team, g.get("away_team") or "")
    ]
    if not matches:
        return None
    matches.sort(key=lambda g: g.get("commence_time") or "")
    return matches[0]


def find_odds_for_pick(
    team: Optional[str],
    pick_type: str,
    pick_detail: dict,
    games: list[dict],
) -> Optional[str]:
    """
    Walk a /odds response and return the American-odds string for the pick,
    or None if no matching market is available.

    - moneyline → outcomes.h2h matching team name
    - spread    → outcomes.spreads where outcome.point matches the parsed line
    - over_under→ outcomes.totals where outcome.name in {Over, Under} and
                  outcome.point matches the parsed total
    """
    if pick_type == "parlay":
        return None  # parlay-leg odds aren't shown at the parent level
    if not games:
        return None

    if pick_type in ("moneyline", "spread"):
        if not team:
            return None
        game = _find_game_for_team(team, games)
    elif pick_type == "over_under":
        # Need event/team context to pick the right game; over/under picks
        # in our model carry the totals number but not always a team. We
        # match via any team name in pick_detail or rely on the caller.
        team_for_lookup = team or pick_detail.get("team")
        if not team_for_lookup:
            return None
        game = _find_game_for_team(str(team_for_lookup), games)
    else:
        return None  # props handled separately, not here

    if not game:
        return None

    book = _pick_bookmaker(game)
    if not book:
        return None

    markets = {m.get("key"): m for m in (book.get("markets") or [])}

    if pick_type == "moneyline":
        market = markets.get("h2h")
        if not market:
            return None
        for outcome in market.get("outcomes") or []:
            if _team_matches(team, outcome.get("name") or ""):
                price = outcome.get("price")
                if price is not None:
                    return _format_american(int(price))
        return None

    if pick_type == "spread":
        market = markets.get("spreads")
        if not market:
            return None
        line = pick_detail.get("line")
        try:
            target_point = float(str(line).replace("+", "")) if line is not None else None
        except (ValueError, TypeError):
            target_point = None
        for outcome in market.get("outcomes") or []:
            if not _team_matches(team, outcome.get("name") or ""):
                continue
            if target_point is None:
                price = outcome.get("price")
                if price is not None:
                    return _format_american(int(price))
                continue
            point = outcome.get("point")
            if point is not None and abs(float(point) - target_point) < 0.01:
                price = outcome.get("price")
                if price is not None:
                    return _format_american(int(price))
        return None

    if pick_type == "over_under":
        market = markets.get("totals")
        if not market:
            return None
        direction = (pick_detail.get("direction") or "").strip().lower()
        total = pick_detail.get("total")
        try:
            target_point = float(str(total)) if total is not None else None
        except (ValueError, TypeError):
            target_point = None
        for outcome in market.get("outcomes") or []:
            outcome_name = (outcome.get("name") or "").strip().lower()
            if direction and outcome_name != direction:
                continue
            if target_point is None:
                price = outcome.get("price")
                if price is not None:
                    return _format_american(int(price))
                continue
            point = outcome.get("point")
            if point is not None and abs(float(point) - target_point) < 0.01:
                price = outcome.get("price")
                if price is not None:
                    return _format_american(int(price))
        return None

    return None


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

    # Extract team name from pick detail. Tennis picks carry the competitor in `player`.
    pick_team = (pick_detail.get("team") or pick_detail.get("player") or "").lower().strip()

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
