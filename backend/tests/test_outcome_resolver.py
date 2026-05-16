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


# --- Cup-winner moneyline (includes_extra_time + winner_side) ---

def _cup_game(home="Chelsea", away="Manchester City", home_score=1, away_score=1, winner_side=None):
    return GameResult(
        game_id="cup-1",
        sport="SOCCER",
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        completed=True,
        commence_time=datetime(2026, 5, 16, 14, 0, tzinfo=timezone.utc),
        home_short=home if home == "Chelsea" else None,
        away_short="Man City" if away == "Manchester City" else None,
        winner_side=winner_side,
    )

def test_cup_winner_via_pks_resolves_winner_even_when_regulation_tied():
    # 1-1 ET draw, Man City wins on penalties. Without includes_extra_time
    # the resolver would call it a push; with the flag it must use winner_side.
    game = _cup_game(home_score=1, away_score=1, winner_side="away")
    result = resolve_pick(
        "moneyline",
        {"team": "Man City", "includes_extra_time": True},
        game,
    )
    assert result == PickStatus.won

def test_cup_winner_opponent_wins_on_pks():
    game = _cup_game(home_score=1, away_score=1, winner_side="home")
    result = resolve_pick(
        "moneyline",
        {"team": "Man City", "includes_extra_time": True},
        game,
    )
    assert result == PickStatus.lost

def test_cup_winner_falls_back_to_score_when_winner_side_missing():
    # Regulation win, no winner_side populated (e.g., stale data). The flag
    # is set but we still resolve via score compare.
    game = _cup_game(home_score=2, away_score=0, winner_side=None)
    result = resolve_pick(
        "moneyline",
        {"team": "Chelsea", "includes_extra_time": True},
        game,
    )
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


# --- Alias-aware matching: abbreviations not contained in the full name ---

def test_find_matching_game_resolves_vgk_alias():
    """VGK isn't a substring of "Vegas Golden Knights" — needs alias map."""
    game = GameResult(
        game_id="nhl-1",
        sport="NHL",
        home_team="Vegas Golden Knights",
        away_team="Edmonton Oilers",
        home_score=4,
        away_score=2,
        completed=True,
        commence_time=datetime(2026, 4, 27, 23, 0, tzinfo=timezone.utc),
    )
    found = find_matching_game(
        event="VGK",
        pick_detail={"team": "VGK"},
        event_date=datetime(2026, 4, 27, 20, 45, tzinfo=timezone.utc),
        games=[game],
    )
    assert found is not None
    assert found.home_team == "Vegas Golden Knights"


def test_find_matching_game_resolves_sixers_alias():
    """Sixers should match "Philadelphia 76ers" via the alias map."""
    game = GameResult(
        game_id="nba-1",
        sport="NBA",
        home_team="Boston Celtics",
        away_team="Philadelphia 76ers",
        home_score=112,
        away_score=105,
        completed=True,
        commence_time=datetime(2026, 4, 28, 23, 0, tzinfo=timezone.utc),
    )
    found = find_matching_game(
        event="Sixers @ Celtics",
        pick_detail={"team": "Sixers"},
        event_date=datetime(2026, 4, 28, 21, 0, tzinfo=timezone.utc),
        games=[game],
    )
    assert found is not None
    assert found.away_team == "Philadelphia 76ers"


def test_find_matching_game_resolves_halos_alias():
    """Halos should match "Los Angeles Angels"."""
    game = GameResult(
        game_id="mlb-1",
        sport="MLB",
        home_team="Chicago White Sox",
        away_team="Los Angeles Angels",
        home_score=3,
        away_score=7,
        completed=True,
        commence_time=datetime(2026, 4, 27, 23, 0, tzinfo=timezone.utc),
    )
    found = find_matching_game(
        event="LAA @ CHW",
        pick_detail={"team": "Halos"},
        event_date=datetime(2026, 4, 27, 19, 36, tzinfo=timezone.utc),
        games=[game],
    )
    assert found is not None
    assert found.away_team == "Los Angeles Angels"


def test_find_matching_game_ambiguous_returns_none():
    """Two same-team games in the date window → ambiguity → None."""
    g1 = GameResult(
        game_id="mlb-y", sport="MLB",
        home_team="Los Angeles Angels", away_team="Houston Astros",
        home_score=4, away_score=2, completed=True,
        commence_time=datetime(2026, 4, 26, 23, 0, tzinfo=timezone.utc),
    )
    g2 = GameResult(
        game_id="mlb-t", sport="MLB",
        home_team="Los Angeles Angels", away_team="Houston Astros",
        home_score=1, away_score=3, completed=True,
        commence_time=datetime(2026, 4, 27, 23, 0, tzinfo=timezone.utc),
    )
    # event_date right between the two games — both fall inside ±24h
    found = find_matching_game(
        event="LAA",
        pick_detail={"team": "Los Angeles Angels"},
        event_date=datetime(2026, 4, 27, 11, 0, tzinfo=timezone.utc),
        games=[g1, g2],
    )
    assert found is None


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
