from datetime import date
from pathlib import Path

import pytest

from sportpulse.parsers import (
    box_scores_to_json,
    clear_box_score_cache,
    load_box_scores,
    parse_box_score,
    parse_box_scores_from_csv,
    parse_box_scores_from_json,
)


def test_parse_box_score_from_dict():
    score = parse_box_score(
        {
            "home": "Lakers",
            "away": "Celtics",
            "home_score": 112,
            "away_score": 108,
            "played_on": "2026-01-14",
        }
    )
    assert score.home == "Lakers"
    assert score.played_on == date(2026, 1, 14)


def test_parse_box_score_rejects_missing_fields():
    with pytest.raises(ValueError, match="missing required field"):
        parse_box_score({"home": "A", "away": "B"})


def test_parse_box_score_accepts_numeric_strings():
    score = parse_box_score(
        {
            "home": "A",
            "away": "B",
            "home_score": "112",
            "away_score": "108",
        }
    )
    assert score.home_score == 112
    assert score.away_score == 108


def test_parse_box_score_rejects_non_integer_floats():
    with pytest.raises(ValueError, match="home_score must be an integer"):
        parse_box_score(
            {
                "home": "A",
                "away": "B",
                "home_score": 112.5,
                "away_score": 108,
            }
        )


def test_parse_json_accepts_float_whole_numbers():
    text = '{"home":"A","away":"B","home_score":112.0,"away_score":108.0}'
    scores = parse_box_scores_from_json(text)
    assert scores[0].home_score == 112
    assert scores[0].away_score == 108


def test_parse_box_score_rejects_invalid_date():
    with pytest.raises(ValueError, match="invalid played_on"):
        parse_box_score(
            {
                "home": "A",
                "away": "B",
                "home_score": 100,
                "away_score": 90,
                "played_on": "not-a-date",
            }
        )


def test_parse_json_single_game():
    text = '{"home":"A","away":"B","home_score":101,"away_score":99}'
    scores = parse_box_scores_from_json(text)
    assert len(scores) == 1
    assert scores[0].winner() == "A"


def test_parse_json_game_list():
    text = """[
        {"home":"A","away":"B","home_score":90,"away_score":88},
        {"home":"C","away":"D","home_score":77,"away_score":80}
    ]"""
    scores = parse_box_scores_from_json(text)
    assert len(scores) == 2
    assert scores[1].winner() == "D"


def test_parse_json_schedule_wrapper():
    text = """{
        "team": "Lakers",
        "games": [
            {"home":"Lakers","away":"Celtics","home_score":112,"away_score":108}
        ]
    }"""
    scores = parse_box_scores_from_json(text)
    assert len(scores) == 1
    assert scores[0].home == "Lakers"


def test_parse_csv_with_optional_date():
    text = """home,away,home_score,away_score,played_on
Lakers,Celtics,112,108,2026-01-14
Knicks,Heat,95,102,
"""
    scores = parse_box_scores_from_csv(text)
    assert len(scores) == 2
    assert scores[0].played_on == date(2026, 1, 14)
    assert scores[1].played_on is None


def test_parse_csv_rejects_bad_score():
    text = "home,away,home_score,away_score\nA,B,101,not-int\n"
    with pytest.raises(ValueError, match="away_score must be an integer"):
        parse_box_scores_from_csv(text)


def test_load_box_scores_from_json_file(tmp_path: Path):
    path = tmp_path / "games.json"
    path.write_text(
        '[{"home":"A","away":"B","home_score":100,"away_score":98}]',
        encoding="utf-8",
    )
    scores = load_box_scores(path)
    assert len(scores) == 1


def test_load_box_scores_from_csv_file(tmp_path: Path):
    path = tmp_path / "games.csv"
    path.write_text(
        "home,away,home_score,away_score\nA,B,100,98\n",
        encoding="utf-8",
    )
    scores = load_box_scores(path)
    assert scores[0].away_score == 98


def test_load_box_scores_reuses_cache_until_file_changes(tmp_path: Path):
    clear_box_score_cache()
    path = tmp_path / "games.json"
    path.write_text(
        '[{"home":"A","away":"B","home_score":100,"away_score":98}]',
        encoding="utf-8",
    )

    first = load_box_scores(path)
    second = load_box_scores(path)
    assert first is second

    path.write_text(
        '[{"home":"A","away":"B","home_score":101,"away_score":98,"played_on":"2026-01-16"}]',
        encoding="utf-8",
    )
    reloaded = load_box_scores(path)
    assert reloaded is not first
    assert reloaded[0].home_score == 101


def test_box_scores_to_json_matches_summary():
    scores = parse_box_scores_from_json(
        '{"home":"A","away":"B","home_score":100,"away_score":100}'
    )
    payload = box_scores_to_json(scores)
    assert payload[0]["winner"] is None
    assert payload[0]["margin"] == 0
