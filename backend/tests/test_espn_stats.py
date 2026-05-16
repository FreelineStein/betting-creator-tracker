"""
Tests for ESPN scoreboard parsing.
No network calls — feeds canned ESPN payload shapes through the parsers.
Run: ./venv/bin/pytest tests/test_espn_stats.py -v
"""
from app.services.espn_stats import (
    _normalize_prop_name,
    _parse_competitor_score,
    _parse_scoreboard_event,
    _parse_tennis_match,
    team_matches,
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


# --- team_matches (shared loose match) ---

def test_team_matches_alias_sixers_to_76ers():
    # Regression: plain substring previously failed this — "sixers" is not in "philadelphia 76ers".
    assert team_matches("Sixers", "Philadelphia 76ers") is True

def test_team_matches_alias_cavs_to_cavaliers():
    assert team_matches("Cavs", "Cleveland Cavaliers") is True

def test_team_matches_alias_avs_to_avalanche():
    assert team_matches("Avs", "Colorado Avalanche") is True

def test_team_matches_full_name_passes_through():
    assert team_matches("Boston Celtics", "Boston Celtics") is True

def test_team_matches_word_boundary_blocks_false_positive():
    # "Li" must not match "Aliassime" — that's the whole reason _word_match exists.
    assert team_matches("Li", "Aliassime") is False

def test_team_matches_empty_inputs_return_false():
    assert team_matches("", "Lakers") is False
    assert team_matches("Lakers", "") is False
    assert team_matches("", "") is False

def test_team_matches_use_aliases_off():
    # With aliases disabled, "Sixers" no longer maps to "76ers".
    assert team_matches("Sixers", "Philadelphia 76ers", use_aliases=False) is False

def test_team_matches_alias_as_to_athletics():
    # Parser sometimes outputs "A's" (with or without apostrophe). Without
    # this alias, normal pinning fails and the LLM pin fallback picks the
    # wrong-day game from the candidate slate.
    assert team_matches("A's", "Athletics") is True
    assert team_matches("As", "Athletics") is True
    assert team_matches("A's", "Oakland Athletics") is True

def test_team_matches_red_sox_not_white_sox():
    # Regression: a single shared word ("sox") used to be enough to match.
    # That mis-pinned "Red Sox ML" submissions onto White Sox games when
    # both Sox teams played the same day.
    assert team_matches("Red Sox", "White Sox") is False
    assert team_matches("Red Sox", "Boston Red Sox") is True
    assert team_matches("White Sox", "Chicago White Sox") is True
    assert team_matches("Red Sox", "Chicago White Sox") is False


# --- odds_api._team_matches now delegates and inherits alias support ---

def test_odds_api_team_matches_picks_up_alias():
    from app.services.odds_api import _team_matches
    # This previously returned False — substring miss. After unification it's True.
    assert _team_matches("Sixers", "Philadelphia 76ers") is True
    assert _team_matches("Avs", "Colorado Avalanche") is True


# --- _normalize_prop_name (combo prop normalization) ---

def test_normalize_long_form_two_stat_combo():
    # Maxey leg: "points + rebounds" → must reach COMBO_PROPS["pts+reb"].
    assert _normalize_prop_name("points + rebounds") == "pts+reb"

def test_normalize_long_form_three_stat_combo():
    # Brown leg: "points + rebounds + assists" → "pts+reb+ast".
    assert _normalize_prop_name("points + rebounds + assists") == "pts+reb+ast"

def test_normalize_mixed_case_and_spacing():
    assert _normalize_prop_name("Points+Rebounds") == "pts+reb"
    assert _normalize_prop_name("  Points  +  Rebounds  ") == "pts+reb"

def test_normalize_pas_abbreviation():
    # Amen Thompson "PAs" — confirmed Points + Assists.
    assert _normalize_prop_name("PAs") == "pts+ast"
    assert _normalize_prop_name("PA") == "pts+ast"

def test_normalize_pra_abbreviation():
    assert _normalize_prop_name("PRA") == "pts+reb+ast"

def test_normalize_already_canonical():
    # Existing short-form input passes through unchanged.
    assert _normalize_prop_name("pts+reb+ast") == "pts+reb+ast"
    assert _normalize_prop_name("pts+ast") == "pts+ast"

def test_normalize_single_stat_long_form():
    # Single-stat input is short-form'd; the caller's COMBO_PROPS lookup will
    # miss and fall through to the long-form PROP_TO_LABEL path.
    assert _normalize_prop_name("rebounds") == "reb"

def test_normalize_empty_input():
    assert _normalize_prop_name("") == ""
    assert _normalize_prop_name("   ") == ""

def test_normalize_unknown_token_passthrough():
    # Unknown tokens are preserved so we can spot them in logs rather than
    # silently mapping to the wrong stat.
    assert _normalize_prop_name("doinks + dunks") == "doinks+dunks"


# --- _extract_stat now resolves combos via the normalizer ---

def test_extract_stat_resolves_long_form_combo():
    from app.services.espn_stats import _extract_stat
    labels = ["MIN", "PTS", "REB", "AST"]
    stats = ["38", "27", "8", "6"]
    # Brown's leg: "points + rebounds + assists" — totals 27 + 8 + 6 = 41.
    assert _extract_stat(labels, stats, "points + rebounds + assists", "NBA", 0) == 41

def test_extract_stat_resolves_pas_abbreviation():
    from app.services.espn_stats import _extract_stat
    labels = ["MIN", "PTS", "REB", "AST"]
    stats = ["32", "18", "5", "7"]
    # Amen Thompson "PAs" — points + assists — 18 + 7 = 25.
    assert _extract_stat(labels, stats, "PAs", "NBA", 0) == 25


# --- Threshold-achievement props (Double-Double / Triple-Double) ---

def test_double_double_achieved():
    from app.services.espn_stats import _extract_stat
    labels = ["MIN", "PTS", "REB", "AST", "STL", "BLK"]
    stats = ["38", "25", "12", "5", "1", "0"]
    # 25 pts + 12 reb = 2 categories at 10+ → DD achieved → 1.0.
    assert _extract_stat(labels, stats, "Double-Double", "NBA", 0) == 1.0

def test_double_double_not_achieved():
    from app.services.espn_stats import _extract_stat
    labels = ["MIN", "PTS", "REB", "AST", "STL", "BLK"]
    stats = ["38", "25", "8", "5", "1", "0"]
    # Only PTS hits 10+ → 0.0.
    assert _extract_stat(labels, stats, "Double-Double", "NBA", 0) == 0.0

def test_triple_double_achieved():
    from app.services.espn_stats import _extract_stat
    labels = ["MIN", "PTS", "REB", "AST", "STL", "BLK"]
    stats = ["38", "22", "10", "12", "1", "0"]
    # 22 / 10 / 12 → 3 categories at 10+ → TD → 1.0.
    assert _extract_stat(labels, stats, "Triple-Double", "NBA", 0) == 1.0

def test_triple_double_not_achieved_with_dd():
    from app.services.espn_stats import _extract_stat
    labels = ["MIN", "PTS", "REB", "AST", "STL", "BLK"]
    stats = ["38", "22", "10", "9", "1", "0"]
    # 22 / 10 / 9 → 2 categories at 10+ — DD but not TD → 0.0.
    assert _extract_stat(labels, stats, "Triple-Double", "NBA", 0) == 0.0

def test_threshold_prop_case_and_separator_variants():
    from app.services.espn_stats import _extract_stat
    labels = ["MIN", "PTS", "REB", "AST"]
    stats = ["38", "25", "12", "5"]
    # All of these should hit the same DD branch.
    for variant in ("Double-Double", "double-double", "Double Double", "double double"):
        assert _extract_stat(labels, stats, variant, "NBA", 0) == 1.0

def test_threshold_prop_returns_none_when_box_empty():
    from app.services.espn_stats import _extract_stat
    # Box score with none of the relevant categories — can't tell.
    assert _extract_stat(["MIN", "FG"], ["38", "10-15"], "Triple-Double", "NBA", 0) is None
