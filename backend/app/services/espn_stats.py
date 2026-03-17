"""
ESPN unofficial API client — fetches per-game player stats for prop resolution.
Covers NBA, NFL, NHL, MLB with no authentication required.

Endpoints used:
  - Scoreboard: find games by date → get event IDs
  - Summary: get box score with individual player stats
"""
import httpx
import structlog
from datetime import datetime, timedelta
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
