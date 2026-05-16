"""
Pick Parser — takes raw extracted text and returns structured Pick objects.

Handles two input types:
1. Raw text (from caption / whisper / OCR extractors) → send to LLM for parsing
2. Structured JSON (already parsed by the LLM extractor) → deserialize directly

Returns a list of ParsedPick dataclasses ready to be inserted as Pick records.
"""
import json
import re
import structlog
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.config import settings

log = structlog.get_logger()

# Sports we recognize
KNOWN_SPORTS = {"NFL", "NBA", "MLB", "NHL", "CFB", "CBB", "SOCCER", "UFC", "NCAAF", "NCAAB", "WNBA", "PGA", "WBC", "TENNIS"}

PARSE_PROMPT = """You are a sports betting pick extractor. Extract ALL betting picks from the text below.

For each pick found, return a JSON object with this exact structure:
{
  "picks": [
    {
      "sport": "NFL",              // Sport abbreviation. MUST be one of: NFL, NBA, MLB, NHL, CFB, CBB, SOCCER, UFC, NCAAF, NCAAB, WNBA, PGA, WBC, TENNIS. Infer from team/league context if not stated explicitly. PGA is golf only; tennis players (Medvedev, Gauff, Aliassime, Sinner, Alcaraz, Sabalenka, Swiatek, etc., on the ATP/WTA tours) MUST be tagged TENNIS, not PGA. Soccer covers ALL leagues (Premier League, Champions League, MLS, La Liga, etc.) — tag the sport as SOCCER and put the specific league in the `league` field.
      "league": null,              // Required for SOCCER picks: the specific league. Use one of these canonical names when possible: "Premier League", "Championship", "Champions League", "Europa League", "Conference League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "MLS", "Liga MX", "World Cup", "Copa America", "Euros". Infer from team context (Aston Villa + Nottingham Forest in midweek + European cup context = "Europa League"; same teams on a weekend = "Premier League"). If you genuinely can't tell which league, use null. Leave null for all non-SOCCER sports.
      "event": "Chiefs vs Raiders", // Use "Team A vs Team B" format ONLY if both teams are clearly mentioned in the text. If only one team is mentioned, output JUST that team's name (e.g. "Chiefs"). NEVER use placeholders like "Opponent", "TBD", "Unknown", or "Other". The opponent will be looked up downstream.
      "event_date": null,          // ISO date string if mentioned (e.g. "2024-01-15"), otherwise null
      "pick_type": "spread",       // One of: spread, moneyline, over_under, prop, parlay
      "pick_detail": {             // Varies by type:
        // spread:      {"team": "Chiefs", "line": "-3.5"}
        // moneyline:   {"team": "Chiefs"}
        // over_under:  {"direction": "Over", "total": "47.5"}
        // prop:        {"player": "Patrick Mahomes", "prop": "passing yards", "line": "285.5", "direction": "Over"}
        // parlay:      {"legs": [{"text": "Chiefs -3.5", "type": "spread", "detail": {"team": "Chiefs", "line": "-3.5"}, "sport": "NFL", "league": null, "event": "Chiefs vs Raiders"}, ...]}
      },
      "odds": "-110",              // American odds as string (e.g. "-110", "+145"). Null if not mentioned.
      "units": 1.0,                // Units bet as float. Null if not mentioned.
      "confidence": 0.9            // Your confidence this is a real pick (0.0-1.0)
    }
  ],
  "no_picks_reason": null          // If picks is empty, explain why (e.g. "no betting content found")
}

Rules:
- TEAM-NAME → SPORT DISAMBIGUATION: a few team names collide with non-sport entities in your training data and must be forced to the right sport regardless of how they sound:
    - "Mammoth" / "Utah Mammoth" → NHL (Utah's NHL franchise, formerly Utah Hockey Club / Arizona Coyotes). NEVER tag a Mammoth pick as PGA, golf, or anything else.
    - "Hockey Club" / "Utah HC" → NHL (legacy name for the same Utah franchise — by current branding it's Mammoth).
- Only extract REAL picks the creator is making, not examples or historical references
- A pick must have at minimum: pick_type and pick_detail
- ALWAYS infer the sport. Use team names, league context, and common knowledge to determine the sport. For example: "Venezuela -1.5" during March = WBC (World Baseball Classic). College teams during March = CBB. NFL teams = NFL. Never leave sport as null if you can reasonably infer it.
- For `event`: only use "Team A vs Team B" when both teams are stated in the text. If only one team is named, return JUST that team — never fabricate an opponent or use a placeholder word like "Opponent". A downstream step will fill in the matchup from a real schedule.
- PARLAYS: If the creator posted a parlay or same game parlay (SGP), return it as ONE pick with pick_type "parlay" and ALL legs listed in pick_detail.legs. Do NOT also break out the individual legs as separate picks. A parlay is a single bet — return it as a single pick.
- IMPLICIT PARLAY DETECTION: Treat a post as ONE parlay even when the word "parlay" never appears, when ALL of these signals align: (a) the title or header uses a grouping noun like "Trio", "Triple", "Lock Trio", "Slip", "Combo", "Card", "Power Play", "Boost", "X-pack", "Lay", "Lay Slip", "No HR Lay", "Anytime Lay", "No-[stat] Lay", or any "N-pick" / "N-leg" phrasing; (b) several picks follow that share a common header/footer (one analysis link, one odds row, etc.); (c) NO per-pick odds appear next to the individual picks — instead one or two combined odds numbers are shown once, typically at the bottom of the image (e.g. "-104   -183" — these are alternate prices for the same bundle, like PrizePicks flex vs. power-play). When you see this pattern, return ONE parlay pick with each pick as a leg in pick_detail.legs, and use the combined bottom odds as the pick's `odds` (prefer the more-negative number when two are shown, since that's typically the all-must-hit price). Counter-example: posts titled "Today's plays", "Best bets", "X picks I'm on", or "Top picks of the day" with per-pick odds beside each pick are SEPARATE picks, not a parlay — return them individually.
- COMBINED-ODDS PARLAY (per-pick prices PRESENT, combined price ALSO shown): When picks are listed with per-pick prices AND there is ALSO a separate combined odds value displayed as one number distinct from the individual lines — typically at the bottom, on its own line, with no player attached, often labeled "ODDS" / "TOTAL" / "PARLAY" or just standing alone — treat the entire post as ONE parlay. The combined value is the pick's `odds`; the per-pick prices are component prices that you may preserve on each leg's `detail.odds` but DO NOT split the ticket into separate single-bet picks. This is the standard format for "No HR Lay" / "No Goal Lay" / "Anytime No [stat]" themed posts: the user lists each player at their −350-ish single-market price, then writes one combined price like "+120 ODDS" or "+250 PARLAY" at the bottom. Concrete example to recognize: header includes "NO HR LAY" repeated, four MLB hitters each listed with their own −X price, then a separate "+120 ODDS" line at the bottom → ONE parlay pick with four legs and odds "+120", not four singles.
- PRIZEPICKS / FANTASY PICK GAMES (Underdog Fantasy, Sleeper, ParlayPlay, etc.): These platforms do NOT allow single-leg bets — every ticket is a parlay by definition. Recognize them by ANY of these signals (one is enough — do not require all three implicit-parlay signals above):
    - Header phrases: "X-Pick Power Play", "X-Pick Flex Play", "$X to pay $Y", "Entry", "Lineup".
    - UI shape: each pick shows the player on one line plus a team/position/jersey row like "PIT • F • #87", an up/down arrow with a numeric line ("↑ 11" or "↓ 0.5"), a stat name ("Faceoffs Won", "Double-Double", "Triple-Double", "Hitter FS", "Pass+Rush Yards"), and an empty / current stat value below.
  When you see ANY of those, ALWAYS return ONE parlay pick — never separate picks — with each pick as a leg. Each leg's `direction` follows the arrow (↑ = Over, ↓ = Under). Compute the pick's `odds` from "$X to pay $Y" as American odds: ((Y / X) − 1) × 100 with a "+" prefix (e.g. "$1,000 to pay $10,000" → "+900"). If no payout text is present, leave `odds` null.
- MULTI-GAME SGP+ / "Parlay+" bundles: when the ticket has any ONE of the signals below, the ENTIRE ticket is exactly ONE parlay pick — never multiple. This is the most common mistake to avoid: do NOT split into one parlay per inner SGP grouping.
  Signals (any one is enough):
    1. A header containing "SGP+", "SBP+", "Same Game Parlay+", "Parlay+", "X leg Same Game Parlay+", or "X-leg parlay"
    2. An "Includes: N Same Game Parlay" / "Includes: N SGP" line
    3. Two odds shown together at the top of the ticket (e.g. "+588 +735", "+908 +1135") above the per-game groupings
  When you see any of those, return ONE parlay pick:
    - Flatten every leg from every inner SGP into pick_detail.legs in the order they appear.
    - Set the pick's `odds` to the parent combined odds at the top of the ticket. When two odds are shown together, prefer the first (it is usually the boosted/profit-boost price). Examples: "+588 +735" → use "+588"; "+908 +1135" → use "+908".
    - The per-SGP prices written above each inner grouping (e.g. "-131", "-185", "+154", "-114") are component prices for INTERNAL accounting only. Ignore them — never use them as the pick's odds, never split the ticket because of them.
  Worked example: a ticket headed "SGP 8 leg Same Game Parlay+ +588 +735 / Includes: 4 Same Game Parlay® bets" with four inner SGPs of 2 legs each at -131/-185/-150/-194 is ONE parlay pick with 8 legs and odds "+588", not 4 parlays.
- PARLAY LEGS must be structured objects: {"text": "human-readable description", "type": "spread|moneyline|over_under|prop", "detail": {same schema as pick_detail for that type}, "sport": "NBA", "league": null, "event": "Team A vs Team B"}. The "text" field is a short human-readable summary. The "type" and "detail" fields follow the same schema as pick_detail for individual picks. Include "sport", "league" (only for SOCCER legs; null otherwise), and "event" for each leg so they can be resolved independently.
- Do NOT duplicate picks. If content describes the same bet multiple times (e.g. a summary and then details), only return it once.
- PROP NAMES — canonicalize these basketball / football abbreviations to their full long form, and NEVER add a parenthetical gloss. The downstream resolver normalizes long-form prop names; abbreviations and creator-invented expansions break it.
    - "PRA" → "Points + Rebounds + Assists"
    - "PAs" / "PA" → "Points + Assists"  (NOT "Potential Assists" — there is no such stat)
    - "PR" → "Points + Rebounds"
    - "RA" → "Rebounds + Assists"
    - "P+R+A" → "Points + Rebounds + Assists"  (any other "+"-joined shorthand expands the same way)
    - "3PM" / "Made Threes" / "Made 3s" → "Made Threes"
    - "TDs" → "Touchdowns"
    - "HR" / "HRs" → "Home Runs"
    - "Hits + Runs + RBIs" / "H+R+RBI" → "Hits + Runs + RBIs"  (keep MLB combo names spelled out)
  Output the canonical long form as the prop value. No parens, no aliases like "(Potential Assists)" — those are guesses and they're wrong.
- TEAM-TOTAL OVER/UNDER — when the line is on ONE team's count (e.g. "Aston Villa Team Total Goals Over 0.5", "Lakers Team Total Points Under 110.5", "Tigers TT Runs Over 3.5"), emit pick_type="over_under" with detail = {"team": "<team name>", "direction": "Over|Under", "total": "<number>"}. The `team` field MUST be set — otherwise the resolver will sum both teams' scores and get the wrong answer. Game-total over/under (no team — "Game Total Goals Over 2.5") uses detail = {"direction", "total"} as before, no team field.
- HOME TEAM / AWAY TEAM TEAM-TOTAL — when the over/under market is explicitly labeled "Home Team Over/Under N" or "Away Team Over/Under N" (e.g. a header that reads "AWAY TEAM OVER/UNDER 2.5 GOALS" sitting above a "Bayern Munich vs FC Köln" matchup), the line is on whichever side is the home/away team in the matchup — NOT on a specific named team. Emit detail = {"team_side": "home" or "away", "direction": "Over|Under", "total": "<number>"} and DO NOT set the `team` field. The resolver picks the correct team via the matchup's home/away assignment, which is the only reliable source for which side is home vs away (slip layout is ambiguous). The leg "text"/event should still name both teams so it's readable, but the structured detail uses `team_side`, never a guessed team name.
- "N+" / "N OR MORE" PHRASING — when a prop or over/under line is written as "N+" / "N or more" / "Anytime N+" / "At least N" (e.g. "Shots on Target 1+", "Hits 2+", "Touchdowns 1+"), this means ≥N which equals "Over (N − 0.5)". Emit line = (N - 0.5) and direction = "Over" — NEVER store the raw N. Examples: "Shots on Target 1+" → line="0.5", direction="Over"; "Hits 2+" → line="1.5", direction="Over"; "Receptions 5+" → line="4.5", direction="Over". The text/leg label can still read "1+" or "Over 0.5" — pick whichever matches the original phrasing more naturally. Counter-example: "Over 1 Hit" (explicitly stated "Over X") stays as line="1", direction="Over" — that's the literal sportsbook line, not the N+ shorthand.
- BINARY "NO [stat]" / "YES [stat]" PROPS — when the creator phrases a counting prop as a yes/no rather than a numeric line:
    - "No HR" / "No Home Run" / "Won't homer" / "HR Lay" / "No HR Lay" / "Anytime No HR" → line="0.5", direction="Under", text like "Under 0.5 Home Runs"
    - "No Goal" / "Lay Goal" → line="0.5", direction="Under", "Under 0.5 Goals"
    - "No TD" / "Lay TD" / "No Touchdown" → line="0.5", direction="Under", "Under 0.5 Touchdowns"
    - "Anytime TD" / "To Score" / "To Hit" / "Yes [stat]" → line="0.5", direction="Over", "Over 0.5 [Stat]"
    The line MUST be "0.5" for these, NEVER "0" — "Under 0 Home Runs" can never win (0 is the floor), so it's a logical error. Same idea applies to "Over 0" — meaningless. When phrasing implies "any of this stat at all" or "none of this stat at all", the line is always 0.5.
- CUP-WINNER LEGS INSIDE AN SGP — when the slip is a Same Game Parlay on a cup FINAL (FA Cup, Carabao Cup, Copa del Rey, DFB-Pokal, Coppa Italia, Coupe de France, MLS Cup, US Open Cup, etc.) and a leg reads "[Team] To Lift the Cup" / "[Team] To Win the Cup" / "[Team] To Win [Cup name]" / "[Team] To Win the Tournament", treat that leg as `type: "moneyline"` with `detail = {"team": "<the exact team in the text>", "includes_extra_time": true}`. The `includes_extra_time` flag tells the resolver to settle on the FULL-MATCH outcome (regulation + extra time + penalty shootout), NOT the 90-minute scoreline — a cup is decided after extra time / penalties, so a team that wins on PKs still lifts the trophy and the pick wins. The `team` MUST be the team named immediately before "To Lift / To Win" in the text — do NOT substitute another team from MLS, the league standings, or training-data associations. If the slip is NOT an SGP on the final (e.g. a stand-alone futures pick like "Arsenal +600 to win the FA Cup" not tied to a single match), skip the leg / pick — we don't have a resolver for tournament-long futures yet.
- FIRST-HALF (1H) MARKETS — when the bet is on the first half only (any of "1st Half", "First Half", "1H", "H1", or a "1st Half" / "1H" inside a leg label), emit the over/under as usual but ADD `detail.period: "1H"`. This applies to soccer (1H Goals Over/Under), basketball halves, and football halves. Currently the resolver only handles soccer game-total 1H over/under — team-total 1H or non-soccer 1H will sit pending — but always set the period field anyway so the data is faithful and the resolver can grow into it. Example: "Chelsea vs Man City 1st Half Under 1.5 Goals" → `type: "over_under", detail: {"direction": "Under", "total": "1.5", "period": "1H"}`.
- NEVER SUBSTITUTE TEAM OR PLAYER NAMES. If the text says "Man City", the output `team` field MUST be a Man City variant ("Man City", "Manchester City") — never "St. Louis", "City SC", or any other team that sounds adjacent. Same rule for players: copy the name from the text, do not infer or replace from memory. If the name in the text is ambiguous or unreadable, leave the field blank rather than guessing.
- Return {"picks": [], "no_picks_reason": "..."} if no picks found
- Return valid JSON only, no explanation

Text to parse:
"""


@dataclass
class ParsedPick:
    """A structured pick ready to be inserted into the DB."""
    pick_type: str
    pick_detail: dict
    sport: Optional[str] = None
    league: Optional[str] = None
    event: Optional[str] = None
    event_date: Optional[datetime] = None
    odds: Optional[str] = None
    units: Optional[float] = None
    confidence: float = 0.8
    raw_text: Optional[str] = None
    # Populated by opponent enrichment when the pick is matched to a real
    # scheduled game. Carries through to Pick.event_id / Pick.event_provider.
    event_id: Optional[str] = None
    event_provider: Optional[str] = None


async def parse_picks(extracted_text: str, source_url: str = "") -> list[ParsedPick]:
    """
    Main entry point. Takes extracted text, returns list of ParsedPick objects.
    Returns empty list if no picks found or parsing fails.
    """
    if not extracted_text or not extracted_text.strip():
        return []

    # Check if this is already structured JSON from the LLM extractor
    if extracted_text.strip().startswith("{"):
        try:
            data = json.loads(extracted_text)
            if "picks" in data:
                log.info("Input is pre-structured JSON, skipping LLM call", url=source_url)
                return _deserialize_picks(data["picks"], extracted_text)
        except json.JSONDecodeError:
            pass  # Fall through to LLM parsing

    # Raw text — send to LLM
    try:
        result = await _llm_parse(extracted_text)
        picks = _deserialize_picks(result.get("picks", []), extracted_text)
        if not picks:
            log.info(
                "No picks found in text",
                reason=result.get("no_picks_reason"),
                url=source_url,
            )
        return picks
    except Exception as e:
        log.error("Pick parser failed", error=str(e), url=source_url)
        return []


def _deserialize_picks(raw_picks: list[dict], original_text: str) -> list[ParsedPick]:
    """Convert raw LLM output dicts into validated ParsedPick objects."""
    results = []
    for item in raw_picks:
        try:
            pick_type = item.get("pick_type", "").lower()
            if pick_type not in ("spread", "moneyline", "over_under", "prop", "parlay"):
                log.warning("Unknown pick_type, skipping", pick_type=pick_type)
                continue

            pick_detail = item.get("pick_detail")
            if not pick_detail:
                continue

            # Normalize sport
            sport = item.get("sport")
            if sport:
                sport = sport.upper()
                if sport not in KNOWN_SPORTS:
                    sport = _fuzzy_sport(sport)

            # League is only meaningful for SOCCER right now; ignore stray values
            # the LLM might put on other sports.
            league = item.get("league")
            if league and isinstance(league, str):
                league = league.strip() or None
            else:
                league = None
            if sport != "SOCCER":
                league = None

            # Parse event date if present
            event_date = None
            if raw_date := item.get("event_date"):
                try:
                    event_date = datetime.fromisoformat(str(raw_date))
                except (ValueError, TypeError):
                    pass

            # Validate units
            units = item.get("units")
            if units is not None:
                try:
                    units = float(units)
                except (ValueError, TypeError):
                    units = None

            # Normalize parlay legs to structured format
            if pick_type == "parlay" and "legs" in pick_detail:
                pick_detail["legs"] = _normalize_legs(pick_detail["legs"])

            results.append(ParsedPick(
                sport=sport,
                league=league,
                event=item.get("event"),
                event_date=event_date,
                pick_type=pick_type,
                pick_detail=pick_detail,
                odds=item.get("odds"),
                units=units,
                confidence=float(item.get("confidence", 0.8)),
                raw_text=original_text[:500],  # Store first 500 chars of source text
            ))

        except Exception as e:
            log.warning("Failed to deserialize pick", error=str(e), item=item)
            continue

    return results


def _normalize_legs(legs: list) -> list[dict]:
    """Ensure all parlay legs are structured objects with a result field."""
    normalized = []
    for leg in legs:
        if isinstance(leg, str):
            # Legacy string format — wrap in object
            normalized.append({"text": leg, "result": "pending"})
        elif isinstance(leg, dict):
            leg.setdefault("result", "pending")
            leg.setdefault("text", _leg_text_from_detail(leg))
            # Normalize sport tags on legs so e.g. an MLS-tagged leg from the
            # LLM becomes SOCCER, matching the rest of the pipeline.
            sport = leg.get("sport")
            if sport and isinstance(sport, str):
                upper = sport.upper()
                leg["sport"] = upper if upper in KNOWN_SPORTS else (_fuzzy_sport(upper) or upper)
            # League is only carried for SOCCER legs.
            if leg.get("sport") != "SOCCER":
                leg.pop("league", None)
            normalized.append(leg)
        else:
            continue
    return normalized


def _leg_text_from_detail(leg: dict) -> str:
    """Generate readable text from a structured leg if text is missing."""
    detail = leg.get("detail", {})
    leg_type = leg.get("type", "")
    if leg_type == "spread":
        return f"{detail.get('team', '')} {detail.get('line', '')}"
    if leg_type == "moneyline":
        return f"{detail.get('team', '')} ML"
    if leg_type == "over_under":
        return f"{detail.get('direction', 'Over')} {detail.get('total', '')}"
    if leg_type == "prop":
        return f"{detail.get('player', '')} {detail.get('direction', 'Over')} {detail.get('line', '')} {detail.get('prop', '')}"
    return leg.get("text", str(detail))


def _fuzzy_sport(sport_str: str) -> Optional[str]:
    """Best-effort normalization for non-standard sport strings."""
    mappings = {
        "FOOTBALL": "NFL", "BASKETBALL": "NBA", "BASEBALL": "MLB",
        "HOCKEY": "NHL", "COLLEGE FOOTBALL": "CFB", "COLLEGE BASKETBALL": "CBB",
        "GOLF": "PGA", "MMA": "UFC",
        "WORLD BASEBALL CLASSIC": "WBC", "WORLD BASEBALL": "WBC",
        "ATP": "TENNIS", "WTA": "TENNIS", "ITF": "TENNIS",
        # Soccer aliases — sport is always SOCCER, the league lives on `league`.
        "MLS": "SOCCER", "EPL": "SOCCER", "PREMIER LEAGUE": "SOCCER",
        "LA LIGA": "SOCCER", "BUNDESLIGA": "SOCCER", "SERIE A": "SOCCER",
        "LIGUE 1": "SOCCER", "CHAMPIONS LEAGUE": "SOCCER",
        "EUROPA LEAGUE": "SOCCER", "UEFA": "SOCCER", "FUTBOL": "SOCCER",
        "FOOTY": "SOCCER",
    }
    return mappings.get(sport_str.upper())


async def _llm_parse(text: str) -> dict:
    """Call LLM to parse raw text into structured pick data."""
    # Truncate to avoid token waste — picks are usually in first 1000 chars
    truncated = text[:2000]

    if settings.anthropic_api_key:
        return await _anthropic_parse(truncated)
    elif settings.openai_api_key:
        return await _openai_parse(truncated)
    else:
        raise RuntimeError("No LLM API key configured for pick parser")


def extract_json_object(text: str) -> str:
    """
    Pull a JSON object substring from possibly-prosaic LLM output.

    Handles:
      - bare JSON: `{...}`
      - JSON inside a ```json ... ``` fence (with or without preamble)
      - JSON preceded by free-text reasoning, no fence

    Returns the extracted text; caller calls json.loads on it.
    Raises ValueError when no JSON object can be located.
    """
    fence = re.search(r"```(?:json)?\s*\n?(\{[\s\S]*?\})\s*\n?```", text)
    if fence:
        return fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in response")
    return text[start:end + 1]


async def _anthropic_parse(text: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    # 1024 tokens isn't enough for long parlays — an 8-leg SGP+ with full
    # detail per leg overruns and the response gets cut off mid-string,
    # producing JSONDecodeError "Unterminated string". 8192 covers the
    # longest tickets we've seen with margin.
    message = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": PARSE_PROMPT + text,
        }],
    )
    raw = message.content[0].text.strip()
    return json.loads(extract_json_object(raw))


async def _openai_parse(text: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": PARSE_PROMPT + text,
        }],
    )
    return json.loads(response.choices[0].message.content)
