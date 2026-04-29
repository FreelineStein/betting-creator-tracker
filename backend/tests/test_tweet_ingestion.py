"""
Unit tests for the tweet-ingestion helpers that don't require a DB or network.
Run: PYTHONPATH=. ./venv/bin/pytest tests/test_tweet_ingestion.py -v
"""
from app.pipeline.parser import ParsedPick
from app.services.tweet_ingestion import (
    _all_picks_pinned,
    _find_fantasy_score_props,
    _is_fantasy_score_prop,
)


# --- _is_fantasy_score_prop ---

def test_fs_token_is_flagged():
    assert _is_fantasy_score_prop("Hitter FS") is True
    assert _is_fantasy_score_prop("Pitcher FS") is True
    assert _is_fantasy_score_prop("FS") is True

def test_fantasy_score_phrase_is_flagged():
    assert _is_fantasy_score_prop("Fantasy Score") is True
    assert _is_fantasy_score_prop("fantasy points") is True
    assert _is_fantasy_score_prop("Fantasy   Score") is True  # whitespace-tolerant

def test_word_boundary_blocks_faceoffs():
    # Substring "FS" appears inside "Faceoffs" but not at a word boundary —
    # the regex must NOT flag it.
    assert _is_fantasy_score_prop("Faceoffs Won") is False

def test_normal_props_not_flagged():
    assert _is_fantasy_score_prop("points") is False
    assert _is_fantasy_score_prop("rebounds") is False
    assert _is_fantasy_score_prop("passing yards") is False
    assert _is_fantasy_score_prop("Triple-Double") is False

def test_empty_or_non_string_inputs():
    assert _is_fantasy_score_prop("") is False
    assert _is_fantasy_score_prop(None) is False
    assert _is_fantasy_score_prop(123) is False


# --- _find_fantasy_score_props ---

def _prop_pick(player: str, prop: str) -> ParsedPick:
    return ParsedPick(
        pick_type="prop",
        pick_detail={"player": player, "prop": prop, "line": "1", "direction": "Over"},
        sport="NBA",
        event="LAL vs BOS",
    )


def _parlay_with_legs(legs: list[dict]) -> ParsedPick:
    return ParsedPick(
        pick_type="parlay",
        pick_detail={"legs": legs},
        sport="NBA",
        event="multi",
    )


def test_finds_top_level_fs_prop():
    picks = [_prop_pick("Shohei Ohtani", "Hitter FS")]
    found = _find_fantasy_score_props(picks)
    assert len(found) == 1
    assert "Shohei Ohtani" in found[0]
    assert "Hitter FS" in found[0]

def test_finds_fs_inside_parlay_legs():
    parlay = _parlay_with_legs([
        {"type": "prop", "detail": {"player": "LeBron James", "prop": "points"}},
        {"type": "prop", "detail": {"player": "Shohei Ohtani", "prop": "Hitter FS"}},
    ])
    found = _find_fantasy_score_props([parlay])
    assert len(found) == 1
    assert "Shohei Ohtani Hitter FS" in found[0]

def test_clean_parlay_returns_empty():
    parlay = _parlay_with_legs([
        {"type": "prop", "detail": {"player": "Sidney Crosby", "prop": "Faceoffs Won"}},
        {"type": "prop", "detail": {"player": "Jokić", "prop": "Triple-Double"}},
    ])
    assert _find_fantasy_score_props([parlay]) == []

def test_normal_prop_pick_returns_empty():
    assert _find_fantasy_score_props([_prop_pick("Jayson Tatum", "points")]) == []

def test_empty_picks_returns_empty():
    assert _find_fantasy_score_props([]) == []


# --- _all_picks_pinned ---

def _pinned_pick() -> ParsedPick:
    return ParsedPick(
        pick_type="moneyline",
        pick_detail={"team": "Lakers"},
        sport="NBA",
        event="Lakers vs Celtics",
        event_id="401234567",
        event_provider="espn",
    )


def _unpinned_pick() -> ParsedPick:
    return ParsedPick(
        pick_type="moneyline",
        pick_detail={"team": "Lakers"},
        sport="NBA",
        event="Lakers vs Celtics",
    )


def test_all_pinned_when_every_pick_has_event_id():
    assert _all_picks_pinned([_pinned_pick(), _pinned_pick()]) is True


def test_unpinned_top_level_pick_fails_gate():
    assert _all_picks_pinned([_pinned_pick(), _unpinned_pick()]) is False


def test_parlay_with_all_legs_pinned_passes():
    parlay = _parlay_with_legs([
        {"type": "moneyline", "event_id": "1", "detail": {"team": "Lakers"}},
        {"type": "moneyline", "event_id": "2", "detail": {"team": "Heat"}},
    ])
    assert _all_picks_pinned([parlay]) is True


def test_parlay_with_one_unpinned_leg_fails_gate():
    parlay = _parlay_with_legs([
        {"type": "moneyline", "event_id": "1", "detail": {"team": "Lakers"}},
        {"type": "moneyline", "detail": {"team": "Heat"}},  # missing event_id
    ])
    assert _all_picks_pinned([parlay]) is False


def test_parlay_with_no_legs_fails_gate():
    parlay = ParsedPick(pick_type="parlay", pick_detail={"legs": []}, sport="NBA")
    assert _all_picks_pinned([parlay]) is False


def test_empty_pick_list_passes_vacuously():
    # Caller checks for parsed_picks before calling this — so empty in means
    # no picks to gate, which we treat as "pinned" (no-op).
    assert _all_picks_pinned([]) is True
