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
KNOWN_SPORTS = {"NFL", "NBA", "MLB", "NHL", "CFB", "CBB", "MLS", "UFC", "NCAAF", "NCAAB", "WNBA", "PGA", "WBC"}

PARSE_PROMPT = """You are a sports betting pick extractor. Extract ALL betting picks from the text below.

For each pick found, return a JSON object with this exact structure:
{
  "picks": [
    {
      "sport": "NFL",              // Sport abbreviation. MUST be one of: NFL, NBA, MLB, NHL, CFB, CBB, MLS, UFC, NCAAF, NCAAB, WNBA, PGA, WBC. Infer from team/league context if not stated explicitly.
      "event": "Chiefs vs Raiders", // MUST be "Team A vs Team B" format. If only one team is mentioned, infer the opponent from context or use the team name alone.
      "event_date": null,          // ISO date string if mentioned (e.g. "2024-01-15"), otherwise null
      "pick_type": "spread",       // One of: spread, moneyline, over_under, prop, parlay
      "pick_detail": {             // Varies by type:
        // spread:      {"team": "Chiefs", "line": "-3.5"}
        // moneyline:   {"team": "Chiefs"}
        // over_under:  {"direction": "Over", "total": "47.5"}
        // prop:        {"player": "Patrick Mahomes", "prop": "passing yards", "line": "285.5", "direction": "Over"}
        // parlay:      {"legs": ["Chiefs -3.5", "Bills ML", "Over 47.5"]}
      },
      "odds": "-110",              // American odds as string (e.g. "-110", "+145"). Null if not mentioned.
      "units": 1.0,                // Units bet as float. Null if not mentioned.
      "confidence": 0.9            // Your confidence this is a real pick (0.0-1.0)
    }
  ],
  "no_picks_reason": null          // If picks is empty, explain why (e.g. "no betting content found")
}

Rules:
- Only extract REAL picks the creator is making, not examples or historical references
- A pick must have at minimum: pick_type and pick_detail
- ALWAYS infer the sport. Use team names, league context, and common knowledge to determine the sport. For example: "Venezuela -1.5" during March = WBC (World Baseball Classic). College teams during March = CBB. NFL teams = NFL. Never leave sport as null if you can reasonably infer it.
- ALWAYS try to format event as "Team A vs Team B". Use your knowledge of current matchups/schedules to infer the opponent when possible.
- For parlays, list all legs in pick_detail.legs
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
    event: Optional[str] = None
    event_date: Optional[datetime] = None
    odds: Optional[str] = None
    units: Optional[float] = None
    confidence: float = 0.8
    raw_text: Optional[str] = None


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

            results.append(ParsedPick(
                sport=sport,
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


def _fuzzy_sport(sport_str: str) -> Optional[str]:
    """Best-effort normalization for non-standard sport strings."""
    mappings = {
        "FOOTBALL": "NFL", "BASKETBALL": "NBA", "BASEBALL": "MLB",
        "HOCKEY": "NHL", "COLLEGE FOOTBALL": "CFB", "COLLEGE BASKETBALL": "CBB",
        "SOCCER": "MLS", "GOLF": "PGA", "MMA": "UFC",
        "WORLD BASEBALL CLASSIC": "WBC", "WORLD BASEBALL": "WBC",
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


async def _anthropic_parse(text: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": PARSE_PROMPT + text,
        }],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code blocks if present
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


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
