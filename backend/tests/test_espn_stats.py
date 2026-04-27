"""
Tests for ESPN scoreboard parsing.
No network calls — feeds canned ESPN payload shapes through the parsers.
Run: ./venv/bin/pytest tests/test_espn_stats.py -v
"""
from app.services.espn_stats import (
    _parse_competitor_score,
    _parse_scoreboard_event,
    _parse_tennis_match,
)


def _team_event(home_score="112", away_score="105", status_name="STATUS_FINAL"):
    return {
        "id": "401705123",
        "date": "2026-04-26T23:00Z",
        "competitions": [
            {
                "status": {"type": {"name": status_name}},
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": home_score,
                        "team": {"displayName": "Boston Celtics", "shortDisplayName": "Celtics"},
                    },
                    {
                        "homeAway": "away",
                        "score": away_score,
                        "team": {"displayName": "Philadelphia 76ers", "shortDisplayName": "76ers"},
                    },
                ],
            }
        ],
    }


def _tennis_match(p1_score="3", p2_score="1", status_name="STATUS_FINAL"):
    return {
        "id": "tennis-match-1",
        "date": "2026-04-25T17:05Z",
        "status": {"type": {"name": status_name}},
        "competitors": [
            {"score": p1_score, "athlete": {"displayName": "Daniil Medvedev"}},
            {"score": p2_score, "athlete": {"displayName": "Adam Marozsan"}},
        ],
    }


# --- _parse_competitor_score ---

def test_parse_score_int():
    assert _parse_competitor_score({"score": "112"}) == 112

def test_parse_score_missing():
    assert _parse_competitor_score({}) is None

def test_parse_score_empty_string():
    assert _parse_competitor_score({"score": ""}) is None

def test_parse_score_unparseable():
    assert _parse_competitor_score({"score": "TBD"}) is None


# --- _parse_scoreboard_event (team sports) ---

def test_team_event_populates_scores_when_final():
    parsed = _parse_scoreboard_event(_team_event(home_score="112", away_score="105"), "NBA")
    assert parsed is not None
    assert parsed.completed is True
    assert parsed.home_score == 112
    assert parsed.away_score == 105
    assert parsed.home_team == "Boston Celtics"
    assert parsed.away_team == "Philadelphia 76ers"

def test_team_event_in_progress_still_has_partial_scores():
    # Live game: scores present but not yet STATUS_FINAL.
    # The parser captures whatever scores ESPN returns; the completed flag is
    # what get_completed_games_espn filters on.
    parsed = _parse_scoreboard_event(
        _team_event(home_score="58", away_score="62", status_name="STATUS_IN_PROGRESS"),
        "NBA",
    )
    assert parsed is not None
    assert parsed.completed is False
    assert parsed.home_score == 58
    assert parsed.away_score == 62

def test_team_event_pregame_has_none_scores():
    parsed = _parse_scoreboard_event(
        _team_event(home_score="", away_score="", status_name="STATUS_SCHEDULED"),
        "NBA",
    )
    assert parsed is not None
    assert parsed.completed is False
    assert parsed.home_score is None
    assert parsed.away_score is None


# --- _parse_tennis_match ---

def test_tennis_match_populates_set_wins_when_final():
    parsed = _parse_tennis_match(_tennis_match(p1_score="3", p2_score="1"))
    assert parsed is not None
    assert parsed.completed is True
    assert parsed.sport == "TENNIS"
    assert parsed.home_score == 3
    assert parsed.away_score == 1
    assert parsed.home_team == "Daniil Medvedev"
    assert parsed.away_team == "Adam Marozsan"

def test_tennis_match_pregame_has_none_scores():
    parsed = _parse_tennis_match(
        _tennis_match(p1_score="", p2_score="", status_name="STATUS_SCHEDULED")
    )
    assert parsed is not None
    assert parsed.home_score is None
    assert parsed.away_score is None
