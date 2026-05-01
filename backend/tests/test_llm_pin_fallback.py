"""
Unit tests for the LLM pin fallback. The LLM call is mocked — we verify
the no-op guards, the hallucination filter, and that returned matches
are correctly applied to picks/legs.

Run: PYTHONPATH=. ./venv/bin/pytest tests/test_llm_pin_fallback.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.pipeline.parser import ParsedPick
from app.services.espn_stats import ScheduledGame
from app.services.llm_pin_fallback import pin_unmatched_picks


def _game(game_id: str, home: str = "Lakers", away: str = "Rockets") -> ScheduledGame:
    return ScheduledGame(
        game_id=game_id,
        sport="NBA",
        home_team=f"Los Angeles {home}",
        home_short=home,
        away_team=f"Houston {away}",
        away_short=away,
        commence_time=datetime(2026, 4, 27, 23, 0, tzinfo=timezone.utc),
        completed=False,
    )


def _unpinned_prop_pick() -> ParsedPick:
    return ParsedPick(
        pick_type="prop",
        pick_detail={"player": "LeBron James", "prop": "rebounds", "line": "6", "direction": "Over"},
        sport="NBA",
        event="Lakers vs Rockets",
    )


def _pinned_pick() -> ParsedPick:
    return ParsedPick(
        pick_type="moneyline",
        pick_detail={"team": "Lakers"},
        sport="NBA",
        event="Lakers vs Rockets",
        event_id="401869408",
        event_provider="espn",
    )


@pytest.mark.asyncio
async def test_noop_when_kill_switch_off(monkeypatch):
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", False)
    picks = [_unpinned_prop_pick()]
    pinned = await pin_unmatched_picks("text", picks, posted_at=None)
    assert pinned["pinned"] == 0
    assert picks[0].event_id is None


@pytest.mark.asyncio
async def test_noop_when_no_anthropic_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    picks = [_unpinned_prop_pick()]
    pinned = await pin_unmatched_picks("text", picks, posted_at=None)
    assert pinned["pinned"] == 0


@pytest.mark.asyncio
async def test_noop_when_all_picks_pinned(monkeypatch):
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    picks = [_pinned_pick()]
    pinned = await pin_unmatched_picks("text", picks, posted_at=None)
    assert pinned["pinned"] == 0


@pytest.mark.asyncio
async def test_noop_when_no_candidate_games(monkeypatch):
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    with patch(
        "app.services.llm_pin_fallback.get_scheduled_games",
        new=AsyncMock(return_value=[]),
    ):
        pinned = await pin_unmatched_picks("text", [_unpinned_prop_pick()], posted_at=None)
    assert pinned["pinned"] == 0


@pytest.mark.asyncio
async def test_pins_top_level_pick_from_llm_response(monkeypatch):
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    picks = [_unpinned_prop_pick()]
    games = [_game("401869408"), _game("401869999", home="Magic", away="Pistons")]

    fake_message = type("M", (), {
        "content": [type("C", (), {"text": json.dumps({
            "matches": [
                {"pick_index": 0, "leg_index": None, "event_id": "401869408"},
            ],
        })})()],
    })

    with patch(
        "app.services.llm_pin_fallback.get_scheduled_games",
        new=AsyncMock(return_value=games),
    ), patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create = AsyncMock(return_value=fake_message)
        pinned = await pin_unmatched_picks("text", picks, posted_at=None)

    assert pinned["pinned"] == 1
    assert picks[0].event_id == "401869408"
    assert picks[0].event_provider == "espn"
    # event_date must come from the matched game's commence_time, otherwise
    # the homepage falls back to rendering "Today" for these rows.
    assert picks[0].event_date == datetime(2026, 4, 27, 23, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_parlay_parent_event_date_set_from_earliest_leg(monkeypatch):
    """When LLM pins parlay legs, the parent pick.event_date should adopt
    the earliest leg's commence_time so the homepage groups it correctly."""
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    parlay = ParsedPick(
        pick_type="parlay",
        pick_detail={"legs": [
            {"type": "moneyline", "sport": "NBA", "detail": {"team": "Lakers"}},
            {"type": "moneyline", "sport": "NBA", "detail": {"team": "Magic"}},
        ]},
        sport="NBA",
    )
    early = ScheduledGame(
        game_id="early-id", sport="NBA",
        home_team="LA Lakers", home_short="Lakers",
        away_team="Houston Rockets", away_short="Rockets",
        commence_time=datetime(2026, 4, 27, 19, 0, tzinfo=timezone.utc),
        completed=False,
    )
    later = ScheduledGame(
        game_id="later-id", sport="NBA",
        home_team="Orlando Magic", home_short="Magic",
        away_team="Detroit Pistons", away_short="Pistons",
        commence_time=datetime(2026, 4, 27, 23, 0, tzinfo=timezone.utc),
        completed=False,
    )

    fake_message = type("M", (), {
        "content": [type("C", (), {"text": json.dumps({
            "matches": [
                {"pick_index": 0, "leg_index": 0, "event_id": "later-id"},
                {"pick_index": 0, "leg_index": 1, "event_id": "early-id"},
            ],
        })})()],
    })

    with patch(
        "app.services.llm_pin_fallback.get_scheduled_games",
        new=AsyncMock(return_value=[early, later]),
    ), patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create = AsyncMock(return_value=fake_message)
        pinned = await pin_unmatched_picks("text", [parlay], posted_at=None)

    assert pinned["pinned"] == 2
    # Parent should adopt the earliest leg's commence (the 19:00 one).
    assert parlay.event_date == datetime(2026, 4, 27, 19, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_drops_hallucinated_event_id(monkeypatch):
    """The model must only choose event_ids from the candidate list."""
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    picks = [_unpinned_prop_pick()]
    games = [_game("401869408")]

    fake_message = type("M", (), {
        "content": [type("C", (), {"text": json.dumps({
            "matches": [
                {"pick_index": 0, "leg_index": None, "event_id": "999-fabricated"},
            ],
        })})()],
    })

    with patch(
        "app.services.llm_pin_fallback.get_scheduled_games",
        new=AsyncMock(return_value=games),
    ), patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create = AsyncMock(return_value=fake_message)
        pinned = await pin_unmatched_picks("text", picks, posted_at=None)

    assert pinned["pinned"] == 0
    assert picks[0].event_id is None


@pytest.mark.asyncio
async def test_pins_parlay_leg(monkeypatch):
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    parlay = ParsedPick(
        pick_type="parlay",
        pick_detail={"legs": [
            {"type": "moneyline", "sport": "NBA", "detail": {"team": "Lakers"}},
            {"type": "moneyline", "sport": "NBA", "detail": {"team": "Rockets"}, "event_id": "already-set"},
        ]},
        sport="NBA",
    )
    games = [_game("401869408")]

    fake_message = type("M", (), {
        "content": [type("C", (), {"text": json.dumps({
            "matches": [
                {"pick_index": 0, "leg_index": 0, "event_id": "401869408"},
            ],
        })})()],
    })

    with patch(
        "app.services.llm_pin_fallback.get_scheduled_games",
        new=AsyncMock(return_value=games),
    ), patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create = AsyncMock(return_value=fake_message)
        pinned = await pin_unmatched_picks("text", [parlay], posted_at=None)

    assert pinned["pinned"] == 1
    legs = parlay.pick_detail["legs"]
    assert legs[0]["event_id"] == "401869408"
    assert legs[0]["event_provider"] == "espn"
    # Already-set leg is untouched
    assert legs[1]["event_id"] == "already-set"


@pytest.mark.asyncio
async def test_returns_zero_on_llm_exception(monkeypatch):
    """LLM call failure must not raise — fallback fails silently to needs_review."""
    monkeypatch.setattr(settings, "llm_pin_fallback_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    games = [_game("401869408")]

    with patch(
        "app.services.llm_pin_fallback.get_scheduled_games",
        new=AsyncMock(return_value=games),
    ), patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client_cls.return_value.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
        pinned = await pin_unmatched_picks("text", [_unpinned_prop_pick()], posted_at=None)

    assert pinned["pinned"] == 0
