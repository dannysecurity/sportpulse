from datetime import date

import pytest

from sportpulse.parsers import (
    canonical_field_name,
    normalize_box_score_record,
    normalize_csv_headers,
    parse_box_score,
    parse_box_scores_from_csv,
    parse_box_scores_from_json,
)


def test_canonical_field_name_maps_common_aliases():
    assert canonical_field_name("home_team") == "home"
    assert canonical_field_name("Away Team") == "away"
    assert canonical_field_name("home_pts") == "home_score"
    assert canonical_field_name("gameDate") == "played_on"
    assert canonical_field_name("host") == "home"
    assert canonical_field_name("visitor") == "away"
    assert canonical_field_name("score_home") == "home_score"
    assert canonical_field_name("event_date") == "played_on"
    assert canonical_field_name("unknown_field") is None


def test_normalize_box_score_record_maps_camel_case_json():
    record = normalize_box_score_record(
        {
            "homeTeam": "Lakers",
            "awayTeam": "Celtics",
            "homeScore": 112,
            "awayScore": 108,
            "gameDate": "2026-01-10",
        }
    )
    assert record == {
        "home": "Lakers",
        "away": "Celtics",
        "home_score": 112,
        "away_score": 108,
        "played_on": "2026-01-10",
    }


def test_parse_box_score_accepts_historical_aliases():
    score = parse_box_score(
        {
            "home_team": " Lakers ",
            "away_team": " Celtics ",
            "home_pts": "112",
            "away_pts": "108",
            "game_date": "2026-01-14",
        }
    )
    assert score.home == "Lakers"
    assert score.away == "Celtics"
    assert score.home_score == 112
    assert score.played_on == date(2026, 1, 14)


def test_parse_json_historical_export_wrapper():
    text = """{
        "games": [
            {
                "homeTeam": "A",
                "awayTeam": "B",
                "homeScore": 101,
                "awayScore": 99,
                "gameDate": "2026-01-10"
            }
        ]
    }"""
    scores = parse_box_scores_from_json(text)
    assert len(scores) == 1
    assert scores[0].winner() == "A"


def test_normalize_csv_headers_maps_spreadsheet_columns():
    mapping = normalize_csv_headers(
        ["home_team", "away_team", "home_pts", "away_pts", "game_date"]
    )
    assert mapping == {
        "home_team": "home",
        "away_team": "away",
        "home_pts": "home_score",
        "away_pts": "away_score",
        "game_date": "played_on",
    }


def test_parse_csv_historical_export_headers():
    text = """home_team,away_team,home_pts,away_pts,game_date
Lakers,Celtics,112,108,2026-01-10
Warriors,Lakers,99,102,2026-01-12
"""
    scores = parse_box_scores_from_csv(text)
    assert len(scores) == 2
    assert scores[0].home == "Lakers"
    assert scores[1].winner() == "Lakers"


def test_parse_csv_host_visitor_aliases():
    text = """host,visitor,score_home,score_away,event_date
Lakers,Celtics,112,108,2026-01-10
Warriors,Lakers,99,102,2026-01-12
"""
    scores = parse_box_scores_from_csv(text)
    assert len(scores) == 2
    assert scores[0].away == "Celtics"
    assert scores[1].played_on.isoformat() == "2026-01-12"


def test_parse_csv_rejects_missing_required_alias_columns():
    text = "home_team,away_team,home_pts\nA,B,100\n"
    with pytest.raises(ValueError, match="missing required column"):
        parse_box_scores_from_csv(text)
