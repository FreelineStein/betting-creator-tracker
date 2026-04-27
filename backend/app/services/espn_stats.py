"""
ESPN unofficial API client — fetches per-game player stats for prop resolution.
Covers NBA, NFL, NHL, MLB with no authentication required.

Endpoints used:
  - Scoreboard: find games by date → get event IDs
  - Summary: get box score with individual player stats
"""
import httpx
import structlog
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

log = structlog.get_logger()

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

# Map our sport abbreviations to ESPN sport/league paths
LEAGUE_MAP: dict[str, tuple[str, str]] = {
    "NBA":   ("basketball", "nba"),
    "WNBA":  ("basketball", "wnba"),
    "CBB":   ("basketball", "mens-college-basketball"),
    "NCAAB": ("basketball", "mens-college-basketball"),
    "NFL":   ("football", "nfl"),
    "CFB":   ("football", "college-football"),
    "NCAAF": ("football", "college-football"),
    "NHL":   ("hockey", "nhl"),
    "MLB":   ("baseball", "mlb"),
}

# Map prop stat names to ESPN box score label names per sport
# NBA labels: MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB, DREB, PF, +/-
# NFL passing: C/ATT, YDS, AVG, TD, INT, SACKS, QBR, RTG
# NFL rushing: CAR, YDS, AVG, TD, LONG
# NFL receiving: REC, YDS, AVG, TD, LONG, TGTS
# NHL skater: BS, HT, TK, +/-, TOI, PPTOI, SHTOI, ESTOI, SHFT, G, YTDG, A, S, SM, SOG, ...
# MLB batting: H-AB, AB, R, H, RBI, HR, BB, K, #P, AVG, OBP, SLG
PROP_TO_LABEL: dict[str, list[tuple[str, str, Optional[int]]]] = {
    # (espn_label, sport, category_index or None for any)
    # NBA
    "points":     [("PTS", "NBA", None), ("PTS", "CBB", None), ("PTS", "WNBA", None)],
    "rebounds":    [("REB", "NBA", None), ("REB", "CBB", None)],
    "assists":     [("AST", "NBA", None), ("AST", "CBB", None)],
    "steals":      [("STL", "NBA", None)],
    "blocks":      [("BLK", "NBA", None)],
    "turnovers":   [("TO", "NBA", None)],
    "3-pointers":  [("3PT", "NBA", None)],
    "three pointers": [("3PT", "NBA", None)],
    "three pointers made": [("3PT", "NBA", None)],
    "threes":      [("3PT", "NBA", None)],
    "made threes": [("3PT", "NBA", None)],
    # NFL
    "passing yards":  [("YDS", "NFL", 0), ("YDS", "CFB", 0)],
    "rushing yards":  [("YDS", "NFL", 1), ("YDS", "CFB", 1)],
    "receiving yards": [("YDS", "NFL", 2), ("YDS", "CFB", 2)],
    "touchdowns":     [("TD", "NFL", None), ("TD", "CFB", None)],
    "passing touchdowns": [("TD", "NFL", 0), ("TD", "CFB", 0)],
    "rushing touchdowns": [("TD", "NFL", 1)],
    "receptions":     [("REC", "NFL", 2), ("REC", "CFB", 2)],
    "completions":    [("C/ATT", "NFL", 0)],
    "interceptions":  [("INT", "NFL", 0)],
    # NHL
    "goals":       [("G", "NHL", None)],
    "saves":       [("SV", "NHL", 3)],
    "shots":       [("SOG", "NHL", None)],
    "shots on goal": [("SOG", "NHL", None)],
    # MLB
    "hits":        [("H", "MLB", 0)],
    "home runs":   [("HR", "MLB", 0)],
    "rbis":        [("RBI", "MLB", 0)],
    "rbi":         [("RBI", "MLB", 0)],
    "runs":        [("R", "MLB", 0)],
    "strikeouts":  [("K", "MLB", None)],
    "walks":       [("BB", "MLB", None)],
}

# Combo props that require summing multiple stats
COMBO_PROPS: dict[str, list[str]] = {
    "pts+reb+ast":  ["PTS", "REB", "AST"],
    "pts+reb":      ["PTS", "REB"],
    "pts+ast":      ["PTS", "AST"],
    "reb+ast":      ["REB", "AST"],
    "pts+reb+ast+stl+blk": ["PTS", "REB", "AST", "STL", "BLK"],
}


@dataclass
class PlayerGameStats:
    player_name: str
    stat_name: str
    stat_value: float
    event_id: str


def _normalize_name(name: str) -> str:
    """Normalize player name for fuzzy matching."""
    return name.lower().strip().replace(".", "").replace("'", "").replace("-", " ")


async def find_player_stat(
    player_name: str,
    prop_name: str,
    sport: str,
    event_date: Optional[datetime] = None,
) -> Optional[PlayerGameStats]:
    """
    Find a player's stat for a specific prop in a recent game.
    Searches games around the event_date (±1 day).
    """
    league_info = LEAGUE_MAP.get(sport)
    if not league_info:
        log.warning("No ESPN league mapping for sport", sport=sport)
        return None

    sport_path, league = league_info

    # Search ±1 day around event_date
    dates_to_check = []
    if event_date:
        for delta in [0, -1, 1]:
            d = event_date + timedelta(days=delta)
            dates_to_check.append(d.strftime("%Y%m%d"))
    else:
        return None

    normalized_player = _normalize_name(player_name)

    for date_str in dates_to_check:
        event_ids = await _get_event_ids(sport_path, league, date_str)
        for event_id in event_ids:
            result = await _search_box_score(
                sport_path, league, event_id, normalized_player, prop_name, sport
            )
            if result:
                return result

    log.info("Player stat not found", player=player_name, prop=prop_name, sport=sport)
    return None


@dataclass
class ScheduledGame:
    """A game from the ESPN scoreboard — used for opponent enrichment at submit time."""
    game_id: str
    sport: str
    home_team: str       # full name e.g. "Cleveland Cavaliers"
    home_short: str      # display name e.g. "Cavaliers"
    away_team: str
    away_short: str
    commence_time: datetime
    completed: bool


# Cache scheduled games per (sport, day-window) for 30 minutes.
_scheduled_cache: dict[str, tuple[datetime, list]] = {}
_SCHEDULED_CACHE_TTL = timedelta(minutes=30)


async def get_scheduled_games(sport: str, days_ahead: int = 4) -> list[ScheduledGame]:
    """
    Fetch upcoming + in-progress games from ESPN's free scoreboard endpoint.
    Used to fill in the opponent for picks that name only one team.

    Walks today + the next `days_ahead - 1` days. ESPN scoreboards are
    keyed by date, and a game in late evening UTC may belong to the next
    day's scoreboard, so we need a small window. No auth, no quota.
    """
    league_info = LEAGUE_MAP.get(sport.upper())
    if not league_info:
        return []
    sport_path, league = league_info

    cache_key = f"{sport}:{days_ahead}"
    now = datetime.now(timezone.utc)
    if cache_key in _scheduled_cache:
        cached_at, cached = _scheduled_cache[cache_key]
        if now - cached_at < _SCHEDULED_CACHE_TTL:
            return cached

    today = now.date()
    dates = [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(days_ahead)]

    games: list[ScheduledGame] = []
    seen_ids: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for date_str in dates:
                resp = await client.get(
                    f"{BASE_URL}/{sport_path}/{league}/scoreboard",
                    params={"dates": date_str},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for event in data.get("events", []) or []:
                    if event.get("id") in seen_ids:
                        continue
                    parsed = _parse_scoreboard_event(event, sport)
                    if parsed:
                        games.append(parsed)
                        seen_ids.add(parsed.game_id)
    except Exception as e:
        log.error("ESPN scoreboard fetch failed", sport=sport, error=str(e))
        return []

    _scheduled_cache[cache_key] = (now, games)
    log.info("Fetched ESPN scheduled games", sport=sport, count=len(games))
    return games


def _parse_scoreboard_event(event: dict, sport: str) -> Optional[ScheduledGame]:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]
    competitors = comp.get("competitors") or []
    if len(competitors) < 2:
        return None

    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home or not away:
        return None

    def team_names(c: dict) -> tuple[str, str]:
        team = c.get("team") or {}
        full = team.get("displayName") or team.get("name") or ""
        short = team.get("name") or team.get("shortDisplayName") or full
        return full, short

    home_full, home_short = team_names(home)
    away_full, away_short = team_names(away)

    raw_date = event.get("date")
    if not raw_date:
        return None
    try:
        commence = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    except ValueError:
        return None

    status = (comp.get("status") or {}).get("type") or {}
    completed = status.get("name") == "STATUS_FINAL"

    return ScheduledGame(
        game_id=event.get("id", ""),
        sport=sport,
        home_team=home_full,
        home_short=home_short,
        away_team=away_full,
        away_short=away_short,
        commence_time=commence,
        completed=completed,
    )


# Team-nickname aliases — needed because abbreviations like "Cavs" / "Mavs"
# / "Sixers" / "T-Wolves" are NOT substrings of the official team names
# ("Cavaliers", "Mavericks", "76ers", "Timberwolves"). Only NBA needs this
# heavily; other leagues' common nicknames are usually substrings of the
# full name (e.g. "Lakers" in "Los Angeles Lakers" works without aliasing).
_NICKNAME_ALIASES: dict[str, str] = {
    # NBA
    "cavs": "cavaliers",
    "mavs": "mavericks",
    "sixers": "76ers",
    "76ers": "76ers",
    "t-wolves": "timberwolves",
    "twolves": "timberwolves",
    "wolves": "timberwolves",
    "blazers": "trail blazers",
    "trail blazers": "trail blazers",
    # NFL — most common informal forms that aren't substrings
    "niners": "49ers",
    "49ers": "49ers",
    "bucs": "buccaneers",
    "jags": "jaguars",
    # NHL
    "habs": "canadiens",
    "preds": "predators",
    "caps": "capitals",
    "leafs": "maple leafs",
    # MLB
    "d-backs": "diamondbacks",
    "dbacks": "diamondbacks",
    "sox": "red sox",  # ambiguous w/ White Sox; bidirectional matching handles either
}


def _normalize_team_query(name: str) -> str:
    n = name.strip().lower()
    return _NICKNAME_ALIASES.get(n, n)


def find_opponent_in_schedule(
    team: str, games: list[ScheduledGame]
) -> Optional[tuple[str, datetime]]:
    """
    Given a team name like "Cavs" or "Cleveland Cavaliers", find the
    matching scheduled game and return (opponent_full_name, commence_time).

    Match strategy (in order of preference):
      1. exact match on full or short name
      2. resolve common abbreviations via _NICKNAME_ALIASES, then containment
      3. substring containment in either direction
    Picks the soonest matching game when several exist.
    """
    if not team or not games:
        return None
    needle = _normalize_team_query(team)
    if not needle:
        return None

    candidates: list[tuple[ScheduledGame, str]] = []
    for game in games:
        for full, short, opponent in [
            (game.home_team, game.home_short, game.away_team),
            (game.away_team, game.away_short, game.home_team),
        ]:
            full_l = full.lower()
            short_l = short.lower()
            if (
                needle == full_l
                or needle == short_l
                or needle in full_l
                or needle in short_l
                or short_l in needle
            ):
                candidates.append((game, opponent))
                break

    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0].commence_time)
    soonest, opponent = candidates[0]
    return opponent, soonest.commence_time


async def _get_event_ids(sport_path: str, league: str, date_str: str) -> list[str]:
    """Get event IDs for games on a specific date."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/{sport_path}/{league}/scoreboard",
                params={"dates": date_str},
            )
            resp.raise_for_status()
            data = resp.json()

        events = data.get("events", [])
        # Only return completed games
        ids = []
        for event in events:
            competitions = event.get("competitions", [])
            if competitions:
                status = competitions[0].get("status", {}).get("type", {}).get("name", "")
                if status == "STATUS_FINAL":
                    ids.append(event["id"])
        return ids

    except Exception as e:
        log.error("ESPN scoreboard fetch failed", error=str(e))
        return []


async def _search_box_score(
    sport_path: str,
    league: str,
    event_id: str,
    normalized_player: str,
    prop_name: str,
    sport: str,
) -> Optional[PlayerGameStats]:
    """Search a game's box score for a player's stat."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/{sport_path}/{league}/summary",
                params={"event": event_id},
            )
            resp.raise_for_status()
            data = resp.json()

        boxscore = data.get("boxscore", {})
        teams = boxscore.get("players", [])

        for team in teams:
            stat_categories = team.get("statistics", [])
            for cat_index, category in enumerate(stat_categories):
                labels = category.get("labels", [])
                athletes = category.get("athletes", [])

                for athlete_data in athletes:
                    athlete = athlete_data.get("athlete", {})
                    name = _normalize_name(athlete.get("displayName", ""))

                    # Fuzzy match: check if player name matches
                    if not _names_match(normalized_player, name):
                        continue

                    # Find the right stat
                    stat_value = _extract_stat(
                        labels, athlete_data.get("stats", []),
                        prop_name, sport, cat_index
                    )
                    if stat_value is not None:
                        return PlayerGameStats(
                            player_name=athlete.get("displayName", ""),
                            stat_name=prop_name,
                            stat_value=stat_value,
                            event_id=event_id,
                        )

        return None

    except Exception as e:
        log.error("ESPN summary fetch failed", event_id=event_id, error=str(e))
        return None


def _names_match(search: str, candidate: str) -> bool:
    """Check if player names match (fuzzy)."""
    if search == candidate:
        return True
    # Check if last name matches and first initial matches
    search_parts = search.split()
    candidate_parts = candidate.split()
    if len(search_parts) >= 2 and len(candidate_parts) >= 2:
        if search_parts[-1] == candidate_parts[-1]:
            if search_parts[0][0] == candidate_parts[0][0]:
                return True
    # Check if search is a substring
    if search in candidate or candidate in search:
        return True
    return False


def _extract_stat(
    labels: list[str],
    stats: list[str],
    prop_name: str,
    sport: str,
    cat_index: int,
) -> Optional[float]:
    """Extract a numeric stat value from the box score labels/stats arrays."""
    prop_lower = prop_name.lower()

    # Check combo props first (pts+reb+ast, etc.)
    combo_labels = COMBO_PROPS.get(prop_lower)
    if combo_labels:
        total = 0.0
        found_any = False
        for lbl in combo_labels:
            if lbl in labels:
                idx = labels.index(lbl)
                if idx < len(stats):
                    val = _parse_stat_value(stats[idx], lbl)
                    if val is not None:
                        total += val
                        found_any = True
        return total if found_any else None

    mappings = PROP_TO_LABEL.get(prop_lower, [])

    for espn_label, mapped_sport, required_cat in mappings:
        # Check sport matches
        if mapped_sport != sport:
            continue
        # Check category index if required
        if required_cat is not None and required_cat != cat_index:
            continue

        if espn_label in labels:
            idx = labels.index(espn_label)
            if idx < len(stats):
                raw = stats[idx]
                return _parse_stat_value(raw, espn_label)

    return None


def _parse_stat_value(raw: str, label: str) -> Optional[float]:
    """Parse a stat string into a numeric value."""
    if not raw or raw == "--":
        return None

    # Handle "made-attempted" format (FG: "11-18", 3PT: "3-5", C/ATT: "22-35")
    if label in ("FG", "3PT", "FT", "C/ATT", "H-AB"):
        parts = raw.split("-")
        if len(parts) == 2:
            try:
                return float(parts[0])  # Return the "made" count
            except ValueError:
                return None

    # Handle time format (TOI: "21:35")
    if ":" in raw and label in ("TOI", "MIN", "PPTOI", "SHTOI", "ESTOI"):
        try:
            parts = raw.split(":")
            return float(parts[0]) + float(parts[1]) / 60
        except (ValueError, IndexError):
            return None

    try:
        return float(raw)
    except ValueError:
        return None
