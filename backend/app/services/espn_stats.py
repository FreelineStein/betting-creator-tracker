"""
ESPN unofficial API client — fetches per-game player stats for prop resolution.
Covers NBA, NFL, NHL, MLB, and Tennis (ATP+WTA) with no authentication required.

Endpoints used:
  - Scoreboard: find games by date → get event IDs (tennis nests matches in groupings)
  - Summary: get box score with individual player stats
"""
import re
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
    # Soccer's "primary" path is arbitrary — we don't resolve soccer props
    # against a single league. Real lookups use _MULTI_LEAGUE_SCOREBOARD.
    "SOCCER": ("soccer", "eng.1"),
}

# Sports where the ESPN scoreboard lives at multiple league paths and we want
# games merged across all of them (e.g., tennis = ATP + WTA tours, soccer
# spans Premier League / Europa / La Liga / etc.).
_MULTI_LEAGUE_SCOREBOARD: dict[str, list[tuple[str, str]]] = {
    "TENNIS": [("tennis", "atp"), ("tennis", "wta")],
    "SOCCER": [
        ("soccer", "eng.1"),               # Premier League
        ("soccer", "eng.fa"),              # FA Cup
        ("soccer", "eng.league_cup"),      # Carabao Cup (EFL Cup)
        ("soccer", "uefa.champions"),      # Champions League
        ("soccer", "uefa.europa"),         # Europa League
        ("soccer", "uefa.europa.conf"),    # Conference League
        ("soccer", "esp.1"),               # La Liga
        ("soccer", "esp.copa_del_rey"),    # Copa del Rey
        ("soccer", "ger.1"),               # Bundesliga
        ("soccer", "ger.dfb_pokal"),       # DFB-Pokal
        ("soccer", "ita.1"),               # Serie A
        ("soccer", "ita.coppa_italia"),    # Coppa Italia
        ("soccer", "fra.1"),               # Ligue 1
        ("soccer", "fra.coupe_de_france"), # Coupe de France
        ("soccer", "por.1"),               # Primeira Liga (Portugal)
        ("soccer", "swe.1"),               # Allsvenskan (Sweden)
        ("soccer", "nor.1"),               # Eliteserien (Norway)
        ("soccer", "usa.1"),               # MLS
        ("soccer", "mex.1"),               # Liga MX
    ],
}

# Human-readable league names for ESPN league keys. Used when we tag a
# ScheduledGame with the league it came from so the UI and pick records can
# show "Europa League" instead of just "Soccer".
_LEAGUE_DISPLAY_NAMES: dict[str, str] = {
    "eng.1": "Premier League",
    "eng.fa": "FA Cup",
    "eng.league_cup": "Carabao Cup",
    "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
    "uefa.europa.conf": "Conference League",
    "esp.1": "La Liga",
    "esp.copa_del_rey": "Copa del Rey",
    "ger.1": "Bundesliga",
    "ger.dfb_pokal": "DFB-Pokal",
    "ita.1": "Serie A",
    "ita.coppa_italia": "Coppa Italia",
    "fra.1": "Ligue 1",
    "fra.coupe_de_france": "Coupe de France",
    "por.1": "Primeira Liga",
    "swe.1": "Allsvenskan",
    "nor.1": "Eliteserien",
    "usa.1": "MLS",
    "mex.1": "Liga MX",
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
    "home run":    [("HR", "MLB", 0)],
    "hr":          [("HR", "MLB", 0)],
    "rbis":        [("RBI", "MLB", 0)],
    "rbi":         [("RBI", "MLB", 0)],
    "runs":        [("R", "MLB", 0)],
    "strikeouts":  [("K", "MLB", None)],
    "walks":       [("BB", "MLB", None)],
}

# Combo props that require summing multiple stats
COMBO_PROPS: dict[str, list[str]] = {
    # NBA / WNBA / CBB
    "pts+reb+ast":  ["PTS", "REB", "AST"],
    "pts+reb":      ["PTS", "REB"],
    "pts+ast":      ["PTS", "AST"],
    "reb+ast":      ["REB", "AST"],
    "pts+reb+ast+stl+blk": ["PTS", "REB", "AST", "STL", "BLK"],
    # MLB combos — DraftKings/FanDuel "Hitter" parlays
    "h+r+rbi":      ["H", "R", "RBI"],
    "h+rbi":        ["H", "RBI"],
    "r+rbi":        ["R", "RBI"],
    "h+r":          ["H", "R"],
}

# Long-form stat names the parser emits, mapped to the short-form tokens used
# in COMBO_PROPS keys. Pass-through entries keep already-short input stable.
_PROP_TOKEN_MAP: dict[str, str] = {
    "points": "pts",   "pts": "pts",
    "rebounds": "reb", "rebs": "reb", "reb": "reb",
    "assists": "ast",  "asts": "ast", "ast": "ast",
    "steals": "stl",   "stl": "stl",
    "blocks": "blk",   "blk": "blk",
    "turnovers": "to", "to": "to",
    # MLB
    "hits": "h",       "h": "h",
    "runs": "r",       "r": "r",
    "rbis": "rbi",     "rbi": "rbi",
    "walks": "bb",     "bb": "bb",
}

# Whole-string abbreviation aliases for combo props as creators write them
# (DraftKings tickets, Twitter shorthand). Matched before tokenization because
# forms like "PAs" / "PRA" have no separator to split on.
_PROP_COMBO_ALIASES: dict[str, str] = {
    "pra": "pts+reb+ast",
    "pr":  "pts+reb",
    "pa":  "pts+ast",
    "pas": "pts+ast",  # plural form seen in tweets — same meaning as "PA"
    "ra":  "reb+ast",
}


def _normalize_prop_name(prop: str) -> str:
    """
    Map a parser-emitted prop name to the canonical short-form used as keys
    in COMBO_PROPS. Single-stat props (e.g. "rebounds") are still emitted in
    short-form ("reb") here, but the PROP_TO_LABEL lookup downstream uses
    long-form keys, so callers should fall back to the un-normalized name
    when COMBO_PROPS doesn't match.

    Examples:
      "points + rebounds + assists" → "pts+reb+ast"
      "Points + Rebounds"           → "pts+reb"
      "PAs"                         → "pts+ast"
    """
    if not prop:
        return ""
    raw = prop.strip().lower()
    # Whole-string abbreviation alias takes precedence (handles "PAs", "PRA").
    alias = _PROP_COMBO_ALIASES.get(raw.replace(" ", ""))
    if alias:
        return alias
    tokens = [t.strip() for t in re.split(r"\s*\+\s*", raw) if t.strip()]
    if not tokens:
        return raw
    mapped = [_PROP_TOKEN_MAP.get(t, t) for t in tokens]
    return "+".join(mapped)


@dataclass
class PlayerGameStats:
    player_name: str
    stat_name: str
    stat_value: float
    event_id: str


def _normalize_name(name: str) -> str:
    """Normalize player name for fuzzy matching."""
    return name.lower().strip().replace(".", "").replace("'", "").replace("-", " ")


async def find_player_stat_in_event(
    sport: str,
    event_id: str,
    player_name: str,
    prop_name: str,
) -> Optional[PlayerGameStats]:
    """
    Look up a player's stat for a specific known ESPN event_id.

    Counterpart to find_player_stat for the resolver's pinned path: skips
    the ±1 day search-across-events because we already know which game
    the pick was for.
    """
    league_info = LEAGUE_MAP.get(sport.upper())
    if not league_info:
        log.warning("No ESPN league mapping for sport", sport=sport)
        return None
    sport_path, league = league_info
    normalized_player = _normalize_name(player_name)
    return await _search_box_score(
        sport_path, league, event_id, normalized_player, prop_name, sport,
    )


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
    """A game from the ESPN scoreboard — used for opponent enrichment at submit time and outcome resolution."""
    game_id: str
    sport: str
    home_team: str       # full name e.g. "Cleveland Cavaliers"
    home_short: str      # display name e.g. "Cavaliers"
    away_team: str
    away_short: str
    commence_time: datetime
    completed: bool
    # Final scores when completed=True. For tennis, these are sets won.
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    # ESPN-reported winner for matches where the score alone is ambiguous
    # (soccer PK shootouts on cup matches: regulation+ET ends tied but
    # competitors[].winner flags the shootout winner). "home" or "away";
    # None when ESPN hasn't called it yet.
    winner_side: Optional[str] = None
    # Human-readable league this game came from. Only populated for sports
    # that fan out across multiple ESPN league paths (SOCCER), so the
    # downstream pick can be tagged with its actual competition.
    league: Optional[str] = None


# Cache scheduled games per (sport, day-window) for 30 minutes.
_scheduled_cache: dict[str, tuple[datetime, list]] = {}
_SCHEDULED_CACHE_TTL = timedelta(minutes=30)


async def get_scheduled_games(
    sport: str,
    days_back: int = 1,
    days_ahead: int = 5,
    anchor_date: Optional[datetime] = None,
) -> list[ScheduledGame]:
    """
    Fetch upcoming + recently-completed games from ESPN's free scoreboard.
    Used to fill in the opponent for picks that name only one team.

    Walks `days_back` days behind through `days_ahead` days forward, anchored
    on `anchor_date` (defaults to "now"). For ingestion of historical tweets
    — replays via /admin/reprocess-url, or a user submitting an old URL via
    /submit — the anchor MUST be the tweet's `posted_at`, otherwise the
    lookup pulls today's slate and we silently pin the pick to the team's
    next game instead of the one the creator actually picked.

    For sports with multiple ESPN tour paths (e.g. tennis ATP + WTA), all
    paths are fetched and merged. Tennis is special-cased — its scoreboard
    returns tournaments, with the actual matches nested inside groupings.
    """
    sport_upper = sport.upper()
    leagues = _MULTI_LEAGUE_SCOREBOARD.get(sport_upper)
    if not leagues:
        single = LEAGUE_MAP.get(sport_upper)
        if not single:
            return []
        leagues = [single]

    now = datetime.now(timezone.utc)
    anchor = anchor_date or now

    # Cache key incorporates the anchor day so retroactive reprocesses don't
    # poison the live-submission cache (and vice versa).
    cache_key = f"{sport}:{days_back}:{days_ahead}:{anchor.date().isoformat()}"
    if cache_key in _scheduled_cache:
        cached_at, cached = _scheduled_cache[cache_key]
        if now - cached_at < _SCHEDULED_CACHE_TTL:
            return cached

    if sport_upper == "TENNIS":
        games = await _fetch_tennis_matches(
            leagues, days_back=days_back, days_ahead=days_ahead, now=anchor,
        )
    else:
        games = await _fetch_team_sport_games(
            sport, leagues, days_back=days_back, days_ahead=days_ahead, now=anchor,
        )

    _scheduled_cache[cache_key] = (now, games)
    log.info(
        "Fetched ESPN scheduled games",
        sport=sport,
        count=len(games),
        anchor=anchor.date().isoformat(),
    )
    return games


async def find_completed_game_by_event_id(
    sport: str,
    event_id: str,
    anchor_date: Optional[datetime] = None,
) -> Optional[ScheduledGame]:
    """
    Look up a specific scheduled/completed game by ESPN event_id.

    Used by the resolver's pinned path: instead of fuzzy-matching by team
    name, we know the exact game from `pick.event_id` set at submission.
    Falls back gracefully — if the scoreboard window doesn't include the
    requested id (sport mismatch, anchor_date too far off), returns None
    and the pick stays pending.
    """
    games = await get_scheduled_games(sport, anchor_date=anchor_date)
    for g in games:
        if g.game_id == event_id:
            return g
    return None


async def get_completed_games_espn(
    sport: str, days_back: int = 3,
) -> list[ScheduledGame]:
    """
    Fetch recently completed games from ESPN's free scoreboard.
    Counterpart to odds_api.get_completed_games — same shape of result, no quota.
    Filters to games marked STATUS_FINAL with both scores populated.
    """
    # days_ahead=1 includes today's date in _fetch_team_sport_games' range(-days_back, days_ahead),
    # so we catch games that finished earlier today.
    games = await get_scheduled_games(sport, days_back=days_back, days_ahead=1)
    return [
        g for g in games
        if g.completed and g.home_score is not None and g.away_score is not None
    ]


# Soccer prop name → ESPN stat key in summary.rosters[].roster[].stats[].
# The public summary endpoint inlines per-player match stats, so we can
# resolve player props without dropping into the core API. Keys verified
# against ESPN's response for UEFA Europa League matches (2026 season).
_SOCCER_PROP_TO_STAT_KEY: dict[str, str] = {
    "shots on target":   "shotsOnTarget",
    "sot":               "shotsOnTarget",
    "shots":             "totalShots",
    "total shots":       "totalShots",
    "goals":             "totalGoals",
    "total goals":       "totalGoals",
    "assists":           "goalAssists",
    "passes":            "totalPasses",
    "total passes":      "totalPasses",
    "accurate passes":   "accuratePasses",
    "saves":             "saves",
    "tackles":           "totalTackles",
    "interceptions":     "interceptions",
    "fouls":             "foulsCommitted",
    "fouls committed":   "foulsCommitted",
    "offsides":          "offsides",
    "yellow cards":      "yellowCards",
    "red cards":         "redCards",
    "crosses":           "totalCrosses",
}


# Any soccer league key works for summary lookups — ESPN uses the event_id
# directly and ignores the league path in the URL. Picking one cuts the
# branching out of the player-stat fetch.
_SOCCER_SUMMARY_LEAGUE = "eng.1"


async def find_soccer_player_stat_in_event(
    event_id: str,
    player_name: str,
    prop_name: str,
) -> Optional[PlayerGameStats]:
    """
    Look up a soccer player's per-match stat from ESPN's public summary
    endpoint. Walks `summary.rosters[].roster[].stats[]` matching the
    player by normalized display name and the stat by the prop→key map.

    Returns None if the prop isn't supported, the match isn't found, or
    the player isn't on either roster (didn't appear).
    """
    stat_key = _SOCCER_PROP_TO_STAT_KEY.get((prop_name or "").lower().strip())
    if not stat_key:
        log.info("Unsupported soccer prop", prop=prop_name)
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/soccer/{_SOCCER_SUMMARY_LEAGUE}/summary",
                params={"event": event_id},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as e:
        log.error("ESPN soccer summary fetch failed", event_id=event_id, error=str(e))
        return None

    rosters = data.get("rosters") or []
    if not rosters:
        return None

    normalized_player = _normalize_name(player_name)
    for team_block in rosters:
        for entry in (team_block.get("roster") or []):
            ath = entry.get("athlete") or {}
            name = ath.get("displayName") or ath.get("fullName") or ""
            if _normalize_name(name) != normalized_player:
                continue
            for s in entry.get("stats") or []:
                if s.get("name") != stat_key:
                    continue
                raw_val = s.get("value")
                if raw_val is None:
                    continue
                try:
                    value = float(raw_val)
                except (TypeError, ValueError):
                    continue
                return PlayerGameStats(
                    player_name=name,
                    stat_name=stat_key,
                    stat_value=value,
                    event_id=event_id,
                )
    return None


async def get_first_inning_runs(event_id: str) -> Optional[int]:
    """
    Total first-inning runs across both teams for an MLB game.

    Reads `header.competitions[0].competitors[].linescores[0].displayValue`
    from ESPN's summary endpoint — a string like "0" or "2" giving runs
    scored in that inning by that team. Sums home + away to get the
    combined first-inning total used by NRFI/YRFI resolution.

    Returns None if the game isn't found, isn't final, or doesn't carry
    a parsable linescore. Callers should treat None as "leave pending".
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/baseball/mlb/summary",
                params={"event": event_id},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as e:
        log.error("ESPN first-inning fetch failed", event_id=event_id, error=str(e))
        return None

    header = data.get("header") or {}
    competitions = header.get("competitions") or []
    if not competitions:
        return None
    competitors = competitions[0].get("competitors") or []

    total = 0
    seen_any_inning = False
    for c in competitors:
        linescores = c.get("linescores") or []
        if not linescores:
            continue
        first = linescores[0] if isinstance(linescores[0], dict) else None
        if not first:
            continue
        raw = first.get("displayValue")
        try:
            runs = int(raw)
        except (TypeError, ValueError):
            continue
        total += runs
        seen_any_inning = True
    return total if seen_any_inning else None


def _parse_competitor_score(competitor: dict) -> Optional[int]:
    """Pull final score from an ESPN competitor entry. Returns None if absent or unparseable."""
    raw = competitor.get("score")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def _fetch_team_sport_games(
    sport: str,
    leagues: list[tuple[str, str]],
    days_back: int,
    days_ahead: int,
    now: datetime,
) -> list[ScheduledGame]:
    today = now.date()
    dates = [
        (today + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(-days_back, days_ahead)
    ]
    games: list[ScheduledGame] = []
    seen_ids: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for sport_path, league in leagues:
                league_display = _LEAGUE_DISPLAY_NAMES.get(league)
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
                        parsed = _parse_scoreboard_event(event, sport, league_display)
                        if parsed:
                            games.append(parsed)
                            seen_ids.add(parsed.game_id)
    except Exception as e:
        log.error("ESPN scoreboard fetch failed", sport=sport, error=str(e))
        return []
    return games


async def _fetch_tennis_matches(
    leagues: list[tuple[str, str]],
    days_back: int = 1,
    days_ahead: int = 5,
    now: Optional[datetime] = None,
) -> list[ScheduledGame]:
    """
    Tennis: each scoreboard "event" is a tournament. The actual matches live at
    event.groupings[].competitions[]. Competitors carry an `athlete` block
    instead of `team`. We flatten across men's/women's singles + doubles, plus
    ATP and WTA tours, into one match list.

    Walks a date window so historical match results stay reachable for outcome
    resolution; the no-param scoreboard endpoint only returns today's slate.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today = now.date()
    dates = [
        (today + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(-days_back, days_ahead)
    ]

    games: list[ScheduledGame] = []
    seen_ids: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for sport_path, league in leagues:
                for date_str in dates:
                    resp = await client.get(
                        f"{BASE_URL}/{sport_path}/{league}/scoreboard",
                        params={"dates": date_str},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for tournament in data.get("events", []) or []:
                        for grouping in tournament.get("groupings") or []:
                            for match in grouping.get("competitions") or []:
                                parsed = _parse_tennis_match(match)
                                if parsed and parsed.game_id not in seen_ids:
                                    games.append(parsed)
                                    seen_ids.add(parsed.game_id)
    except Exception as e:
        log.error("ESPN tennis scoreboard fetch failed", error=str(e))
        return []
    return games


def _parse_tennis_match(match: dict) -> Optional[ScheduledGame]:
    competitors = match.get("competitors") or []
    if len(competitors) < 2:
        return None

    def athlete_names(c: dict) -> tuple[str, str]:
        a = c.get("athlete") or {}
        full = a.get("displayName") or a.get("fullName") or ""
        short = full.split()[-1] if full else (a.get("shortName") or "")
        return full, short

    p1_full, p1_short = athlete_names(competitors[0])
    p2_full, p2_short = athlete_names(competitors[1])
    if not p1_full or not p2_full:
        return None

    raw_date = match.get("date") or match.get("startDate")
    if not raw_date:
        return None
    try:
        commence = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    except ValueError:
        return None

    status = (match.get("status") or {}).get("type") or {}
    completed = status.get("name") == "STATUS_FINAL"

    return ScheduledGame(
        game_id=match.get("id", ""),
        sport="TENNIS",
        home_team=p1_full,
        home_short=p1_short,
        away_team=p2_full,
        away_short=p2_short,
        commence_time=commence,
        completed=completed,
        home_score=_parse_competitor_score(competitors[0]),
        away_score=_parse_competitor_score(competitors[1]),
    )


def _parse_scoreboard_event(
    event: dict, sport: str, league: Optional[str] = None,
) -> Optional[ScheduledGame]:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]
    competitors = comp.get("competitors") or []
    if len(competitors) < 2:
        return None

    # Most leagues label competitors with home/away. Tennis (and a few other
    # individual-sport ESPN feeds) don't — fall back to first/second order so
    # we still capture the matchup.
    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home or not away:
        home, away = competitors[0], competitors[1]

    def team_names(c: dict) -> tuple[str, str]:
        team = c.get("team") or c.get("athlete") or {}
        full = team.get("displayName") or team.get("name") or team.get("shortName") or ""
        short = team.get("shortDisplayName") or team.get("name") or full
        return full, short

    home_full, home_short = team_names(home)
    away_full, away_short = team_names(away)
    if not home_full or not away_full:
        return None

    raw_date = event.get("date")
    if not raw_date:
        return None
    try:
        commence = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    except ValueError:
        return None

    status = (comp.get("status") or {}).get("type") or {}
    # ESPN exposes a boolean `completed` on status.type that's true for
    # any terminal state — STATUS_FINAL (NBA/NFL/MLB/NHL), STATUS_FULL_TIME
    # (soccer regular time), STATUS_AET / STATUS_PEN (soccer extra-time /
    # penalties), tennis match-end statuses, etc. Trust that flag instead
    # of string-matching STATUS_FINAL only.
    completed = bool(status.get("completed", False))
    # Fallback for any odd cases where the flag is missing but the name
    # clearly indicates finality.
    if not completed and status.get("name") in {
        "STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_AET", "STATUS_PEN",
    }:
        completed = True

    winner_side: Optional[str] = None
    if home.get("winner") is True:
        winner_side = "home"
    elif away.get("winner") is True:
        winner_side = "away"

    return ScheduledGame(
        game_id=event.get("id", ""),
        sport=sport,
        home_team=home_full,
        home_short=home_short,
        away_team=away_full,
        away_short=away_short,
        commence_time=commence,
        completed=completed,
        home_score=_parse_competitor_score(home),
        away_score=_parse_competitor_score(away),
        winner_side=winner_side,
        league=league,
    )


# Team-nickname aliases — needed because betting-Twitter abbreviations like
# "Cavs" / "Mavs" / "Avs" / "Sixers" / "T-Wolves" are NOT substrings of the
# official team names ("Cavaliers", "Mavericks", "Avalanche", "76ers",
# "Timberwolves"). When you find a missed alias, add a row here — see the
# "team_alias_miss" log line below for what to add.
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
    "dubs": "warriors",
    # NFL — abbreviations that aren't substrings of the official names
    "niners": "49ers",
    "49ers": "49ers",
    "bucs": "buccaneers",
    "jags": "jaguars",
    "skins": "commanders",      # legacy abbr for old name
    "iggles": "eagles",
    # NHL
    "avs": "avalanche",
    "vgk": "vegas",
    "habs": "canadiens",
    "preds": "predators",
    "caps": "capitals",
    "leafs": "maple leafs",
    "isles": "islanders",
    "sens": "senators",
    "jackets": "blue jackets",
    "bjs": "blue jackets",
    "yotes": "coyotes",
    "nucks": "canucks",
    "canes": "hurricanes",
    "bolts": "lightning",
    "lighting": "lightning",     # common typo, missing the second "n"
    "wild": "wild",
    "stars": "stars",
    # MLB
    "d-backs": "diamondbacks",
    "dbacks": "diamondbacks",
    "diamondbacks": "diamondbacks",
    "sox": "red sox",            # ambiguous w/ White Sox; bidirectional matching handles either
    "bosox": "red sox",
    "chisox": "white sox",
    "m's": "mariners",
    "ms": "mariners",
    "a's": "athletics",
    "as": "athletics",           # parser sometimes drops the apostrophe
    "stros": "astros",
    "halos": "angels",
    "bucs-mlb": "pirates",       # disambiguates from Buccaneers if the parser ever feeds full text
}


def _normalize_team_query(name: str) -> str:
    n = name.strip().lower()
    return _NICKNAME_ALIASES.get(n, n)


def _words(s: str) -> set[str]:
    """Split a name into lowercase words on whitespace and hyphens."""
    return {w for w in re.split(r"[\s\-]+", s.strip().lower()) if w}


def _word_match(needle: str, candidate: str) -> bool:
    """
    True if one of (needle, candidate) is a whole-word subset of the
    other, case-insensitive. "Red Sox" no longer matches "White Sox" via
    the shared word "Sox" — earlier intersection-based logic let "Red Sox"
    moneylines mis-pin to a White Sox game when both played the same day.
    """
    if not needle or not candidate:
        return False
    n_words = _words(needle)
    c_words = _words(candidate)
    if not n_words or not c_words:
        return False
    return n_words <= c_words or c_words <= n_words


def team_matches(query: str, candidate: str, *, use_aliases: bool = True) -> bool:
    """
    Shared loose team-name match used by both ESPN scoreboard lookups and
    Odds API resolution. Combines _NICKNAME_ALIASES with whole-word matching
    so abbreviations like "Cavs", "Sixers", "Avs" resolve to their canonical
    names without the false positives a plain substring check would produce
    (e.g. "Li" must not match "Aliassime").
    """
    if not query or not candidate:
        return False
    needle = _normalize_team_query(query) if use_aliases else query.strip().lower()
    return _word_match(needle, candidate)


def find_opponent_in_schedule(
    team: str,
    games: list[ScheduledGame],
    *,
    anchor_date: Optional[datetime] = None,
) -> Optional[tuple[str, str, datetime, str, Optional[str]]]:
    """
    Given a team or player name like "Cavs", "Cleveland Cavaliers", or
    "Medvedev", find the matching scheduled game.

    Returns (matched_team_canonical, opponent_canonical, commence_time, game_id, league).
    The first two names are the ESPN "short" form (e.g. "Avalanche",
    "Cavaliers") so callers can normalize the user-entered abbreviation away.
    The game_id is ESPN's identifier — callers persist it so outcome
    resolution can do a direct lookup instead of fuzzy team-name matching.
    `league` is the human-readable competition name (e.g. "Europa League"),
    only populated for sports where it's meaningful (currently SOCCER).

    Match strategy (in order of preference):
      1. exact match on full or short name
      2. resolve common abbreviations via _NICKNAME_ALIASES, then word match
      3. word-boundary match (any shared whole word, case-insensitive)

    When `anchor_date` is provided, picks the game closest to it (most
    common case: MLB/NHL series where the same two teams play on
    consecutive days — picking the soonest blindly would mis-pin a tweet
    about tomorrow's game to today's). Falls back to soonest when no
    anchor is supplied.
    """
    if not team or not games:
        return None
    needle = _normalize_team_query(team)
    if not needle:
        return None

    # (game, matched_team_short, opponent_short)
    candidates: list[tuple[ScheduledGame, str, str]] = []
    for game in games:
        for full, short, opponent_full, opponent_short in [
            (game.home_team, game.home_short, game.away_team, game.away_short),
            (game.away_team, game.away_short, game.home_team, game.home_short),
        ]:
            if _word_match(needle, full) or _word_match(needle, short):
                candidates.append((game, short, opponent_short))
                break

    if not candidates:
        # Visibility hook: when this fires, the team name in the log is the
        # one to add to _NICKNAME_ALIASES (or its canonical form is missing).
        log.warning(
            "team_alias_miss",
            query=team,
            normalized=needle,
            sample_teams=[
                f"{g.away_short} @ {g.home_short}" for g in games[:6]
            ],
        )
        return None
    if anchor_date is not None:
        # Treat naive anchors as UTC — commence_time is always UTC-aware.
        anchor = (
            anchor_date
            if anchor_date.tzinfo
            else anchor_date.replace(tzinfo=timezone.utc)
        )
        # Match by ET calendar date — US sports schedule by ET day. Tweet
        # scraper anchors posted_at at noon UTC so the ET date is stable.
        # The user's pick for "today" means today's ET date; we prefer
        # candidates whose commence_time falls on that same day, then the
        # next day (late-night posts about tomorrow), then prior days.
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        anchor_et_date = anchor.astimezone(et).date()
        def _rank(item):
            commence_et = item[0].commence_time.astimezone(et).date()
            day_delta = (commence_et - anchor_et_date).days
            if day_delta == 0:
                bucket = 0
            elif day_delta > 0:
                bucket = 1
            else:
                bucket = 2
            return (bucket, item[0].commence_time.timestamp())
        candidates.sort(key=_rank)
    else:
        candidates.sort(key=lambda c: c[0].commence_time)
    chosen, matched_short, opponent_short = candidates[0]
    return matched_short, opponent_short, chosen.commence_time, chosen.game_id, chosen.league


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


_DOUBLE_DOUBLE_CATEGORIES = ("PTS", "REB", "AST", "STL", "BLK")


def _resolve_threshold_achievement(
    labels: list[str], stats: list[str], required: int,
) -> Optional[float]:
    """
    Double-Double / Triple-Double: count how many of PTS/REB/AST/STL/BLK the
    player hit 10+ in. Returns 1.0 if they reached the threshold (2 for DD,
    3 for TD), 0.0 otherwise, or None if the box score didn't carry the
    needed categories.
    """
    found_any = False
    count = 0
    for cat in _DOUBLE_DOUBLE_CATEGORIES:
        if cat not in labels:
            continue
        idx = labels.index(cat)
        if idx >= len(stats):
            continue
        val = _parse_stat_value(stats[idx], cat)
        if val is None:
            continue
        found_any = True
        if val >= 10:
            count += 1
    if not found_any:
        return None
    return 1.0 if count >= required else 0.0


def _extract_stat(
    labels: list[str],
    stats: list[str],
    prop_name: str,
    sport: str,
    cat_index: int,
) -> Optional[float]:
    """Extract a numeric stat value from the box score labels/stats arrays."""
    prop_lower = prop_name.lower()
    # Combo props go through the normalizer so parser long-form ("points + rebounds")
    # and creator shorthand ("PAs", "PRA") both reach the canonical COMBO_PROPS keys.
    normalized = _normalize_prop_name(prop_name)

    # Threshold-achievement props (PrizePicks "Triple-Double" / "Double-Double"
    # come through with line=0.5, direction=Over). Return 1.0 if the player
    # achieved it, 0.0 if not — resolve_prop's >/< comparison does the rest.
    if "triple-double" in prop_lower or "triple double" in prop_lower:
        return _resolve_threshold_achievement(labels, stats, required=3)
    if "double-double" in prop_lower or "double double" in prop_lower:
        return _resolve_threshold_achievement(labels, stats, required=2)

    combo_labels = COMBO_PROPS.get(normalized)
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
