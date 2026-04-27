"""
Tests for outcome resolution logic.
No API calls needed — pure logic tests.
Run: ./venv/bin/pytest tests/test_outcome_resolver.py -v
"""
from datetime import datetime, timezone
from app.models.pick import PickStatus
from app.services.espn_stats import ScheduledGame
from app.services.odds_api import GameResult, find_matching_game
from app.services.outcome_resolver import resolve_pick, scheduled_to_game_result


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


def make_tennis_game(p1="Daniil Medvedev", p2="Adam Marozsan", p1_sets=3, p2_sets=1):
    return GameResult(
        game_id="tennis-1",
        sport="TENNIS",
        home_team=p1,
        away_team=p2,
        home_score=p1_sets,
        away_score=p2_sets,
        completed=True,
        commence_time=datetime(2026, 4, 25, 17, 5, tzinfo=timezone.utc),
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


# --- Tennis: pick_detail.player is treated like pick_detail.team ---

def test_moneyline_tennis_player_wins():
    game = make_tennis_game(p1_sets=3, p2_sets=1)
    result = resolve_pick("moneyline", {"player": "Medvedev"}, game)
    assert result == PickStatus.won

def test_moneyline_tennis_player_loses():
    game = make_tennis_game(p1_sets=1, p2_sets=3)
    result = resolve_pick("moneyline", {"player": "Medvedev"}, game)
    assert result == PickStatus.lost

def test_find_matching_game_uses_player_field():
    game = find_matching_game(
        event="Medvedev vs Marozsan",
        pick_detail={"player": "Medvedev"},
        event_date=datetime(2026, 4, 25, 17, 5, tzinfo=timezone.utc),
        games=[make_tennis_game()],
    )
    assert game is not None
    assert game.home_team == "Daniil Medvedev"


# --- ScheduledGame → GameResult conversion ---

def test_scheduled_to_game_result_round_trip():
    sg = ScheduledGame(
        game_id="x1",
        sport="NBA",
        home_team="Boston Celtics",
        home_short="Celtics",
        away_team="Philadelphia 76ers",
        away_short="76ers",
        commence_time=datetime(2026, 4, 26, 23, 0, tzinfo=timezone.utc),
        completed=True,
        home_score=112,
        away_score=105,
    )
    gr = scheduled_to_game_result(sg)
    assert gr.game_id == "x1"
    assert gr.sport == "NBA"
    assert gr.home_team == "Boston Celtics"
    assert gr.away_team == "Philadelphia 76ers"
    assert gr.home_score == 112
    assert gr.away_score == 105
    assert gr.completed is True
    # And the converted shape resolves cleanly through the existing pipeline:
    result = resolve_pick("moneyline", {"team": "Celtics"}, gr)
    assert result == PickStatus.won
