"""
Tests for the pick parser.
Run: ./venv/bin/pytest tests/test_parser.py -v

These tests use the real LLM API — make sure your .env has a key set.
"""
import asyncio
import pytest
from app.pipeline.parser import parse_picks, ParsedPick


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --- Sample texts to test against ---

CLEAR_SPREAD = "Chiefs -3.5 tonight. Lock of the week. 2 units."
CLEAR_ML = "Taking the Eagles ML at +135 for Sunday. 1 unit."
CLEAR_OU = "Going over 47.5 in the Packers/Bears game. Line is -110."
MULTI_PICK = "Two plays today: Lakers -4.5 (-110) and Celtics ML (+120). 1u each."
NO_PICK = "Had a great weekend! Can't wait for the games tonight."
PARLAY = "3-leg parlay: Chiefs -3.5 / Eagles ML / Over 51.5 Rams game. +650"
PROP = "Mahomes over 285.5 passing yards tonight. Great spot at -115."
MESSY_CAPTION = """
🔥🔥 MONDAY NIGHT LOCKS 🔥🔥
Chiefs covering -3.5 💰
Bills moneyline (+105) is FREE MONEY
Hit me up for my full card!
#sportsbetting #nfl
"""


def test_clear_spread():
    picks = run(parse_picks(CLEAR_SPREAD))
    assert len(picks) == 1
    p = picks[0]
    assert p.pick_type == "spread"
    assert p.sport in ("NFL", None)
    assert "Chiefs" in str(p.pick_detail)
    assert p.units == 2.0


def test_clear_moneyline():
    picks = run(parse_picks(CLEAR_ML))
    assert len(picks) == 1
    p = picks[0]
    assert p.pick_type == "moneyline"
    assert p.odds == "+135"
    assert p.units == 1.0


def test_over_under():
    picks = run(parse_picks(CLEAR_OU))
    assert len(picks) == 1
    p = picks[0]
    assert p.pick_type == "over_under"
    assert p.pick_detail.get("direction") == "Over"


def test_multi_pick():
    picks = run(parse_picks(MULTI_PICK))
    assert len(picks) == 2


def test_no_pick():
    picks = run(parse_picks(NO_PICK))
    assert len(picks) == 0


def test_parlay():
    picks = run(parse_picks(PARLAY))
    assert len(picks) == 1
    p = picks[0]
    assert p.pick_type == "parlay"
    assert "legs" in p.pick_detail
    assert len(p.pick_detail["legs"]) == 3


def test_prop():
    picks = run(parse_picks(PROP))
    assert len(picks) == 1
    p = picks[0]
    assert p.pick_type == "prop"
    assert "Mahomes" in str(p.pick_detail)


def test_messy_caption():
    picks = run(parse_picks(MESSY_CAPTION))
    assert len(picks) >= 1  # At minimum should catch the Chiefs spread


def test_empty_input():
    picks = run(parse_picks(""))
    assert picks == []


def test_pre_structured_json():
    """Parser should handle JSON output from the LLM extractor directly."""
    import json
    structured = json.dumps({
        "found": True,
        "picks": [{
            "sport": "NFL",
            "event": "Chiefs vs Raiders",
            "pick_type": "spread",
            "pick_detail": {"team": "Chiefs", "line": "-3.5"},
            "odds": "-110",
            "units": 1.0,
            "confidence": 0.95,
        }],
    })
    picks = run(parse_picks(structured))
    assert len(picks) == 1
    assert picks[0].pick_type == "spread"
