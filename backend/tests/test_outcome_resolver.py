"""
Tests for outcome resolution logic.
No API calls needed — pure logic tests.
Run: ./venv/bin/pytest tests/test_outcome_resolver.py -v
"""
from datetime import datetime, timezone
from app.models.pick import PickStatus
from app.services.odds_api import GameResult, find_matching_game
from app.services.outcome_resolver import resolve_pick


def make_game(home="Kansas City Chiefs", away="Las Vegas Raiders",
              home_score=27, away_score=14):
    return GameResult(
        game_id="test-1",
        sport="NFL",
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        completed=True,
        commence_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )


# --- Moneyline ---

def test_moneyline_win():
    game = make_game(home_score=27, away_score=14)
    result = resolve_pick("moneyline", {"team": "Chiefs"}, game)
    assert result == PickStatus.won

def test_moneyline_loss():
    game = make_game(home_score=14, away_score=27)
    result = resolve_pick("moneyline", {"team": "Chiefs"}, game)
    assert result == PickStatus.lost

def test_moneyline_push():
    game = make_game(home_score=21, away_score=21)
    result = resolve_pick("moneyline", {"team": "Chiefs"}, game)
    assert result == PickStatus.push

def test_moneyline_underdog_win():
    game = make_game(home_score=14, away_score=27)
    result = resolve_pick("moneyline", {"team": "Raiders"}, game)
    assert result == PickStatus.won


# --- Spread ---

def test_spread_favorite_covers():
    # Chiefs -3.5, win by 13 → cover
    game = make_game(home_score=27, away_score=14)
    result = resolve_pick("spread", {"team": "Chiefs", "line": "-3.5"}, game)
    assert result == PickStatus.won

def test_spread_favorite_fails_to_cover():
    # Chiefs -7, win by 3 → don't cover
    game = make_game(home_score=17, away_score=14)
    result = resolve_pick("spread", {"team": "Chiefs", "line": "-7"}, game)
    assert result == PickStatus.lost

def test_spread_underdog_covers():
    # Raiders +7, lose by 3 → cover
    game = make_game(home_score=17, away_score=14)
    result = resolve_pick("spread", {"team": "Raiders", "line": "+7"}, game)
    assert result == PickStatus.won

def test_spread_push():
    # Chiefs -3, win by exactly 3 → push
    game = make_game(home_score=17, away_score=14)
    result = resolve_pick("spread", {"team": "Chiefs", "line": "-3"}, game)
    assert result == PickStatus.push


# --- Over/Under ---

def test_over_hits():
    game = make_game(home_score=27, away_score=24)  # 51 total
    result = resolve_pick("over_under", {"direction": "Over", "total": "47.5"}, game)
    assert result == PickStatus.won

def test_over_misses():
    game = make_game(home_score=17, away_score=14)  # 31 total
    result = resolve_pick("over_under", {"direction": "Over", "total": "47.5"}, game)
    assert result == PickStatus.lost

def test_under_hits():
    game = make_game(home_score=17, away_score=14)  # 31 total
    result = resolve_pick("over_under", {"direction": "Under", "total": "47.5"}, game)
    assert result == PickStatus.won

def test_ou_push():
    game = make_game(home_score=24, away_score=24)  # 48 total
    result = resolve_pick("over_under", {"direction": "Over", "total": "48"}, game)
    assert result == PickStatus.push


# --- Fuzzy game matching ---

def test_fuzzy_match_finds_game():
    games = [make_game()]
    game = find_matching_game(
        event="Chiefs vs Raiders",
        pick_detail={"team": "Chiefs"},
        event_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        games=games,
    )
    assert game is not None
    assert "Chiefs" in game.home_team

def test_fuzzy_match_no_match():
    games = [make_game()]
    game = find_matching_game(
        event="Lakers vs Celtics",
        pick_detail={"team": "Lakers"},
        event_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        games=games,
    )
    assert game is None

def test_fuzzy_match_empty_games():
    game = find_matching_game("Chiefs vs Raiders", {"team": "Chiefs"}, None, [])
    assert game is None
