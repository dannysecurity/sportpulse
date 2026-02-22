from datetime import date

import pytest

from sportpulse.parsers import parse_box_score


def test_parse_box_score_accepts_us_slash_dates():
    score = parse_box_score(
        {
            "home": "A",
            "away": "B",
            "home_score": 100,
            "away_score": 98,
            "played_on": "01/14/2026",
        }
    )
    assert score.played_on == date(2026, 1, 14)


def test_parse_box_score_accepts_us_dash_dates():
    score = parse_box_score(
        {
            "home": "A",
            "away": "B",
            "home_score": 100,
            "away_score": 98,
            "played_on": "01-14-2026",
        }
    )
    assert score.played_on == date(2026, 1, 14)


def test_parse_box_score_prefers_iso_dates():
    score = parse_box_score(
        {
            "home": "A",
            "away": "B",
            "home_score": 100,
            "away_score": 98,
            "played_on": "2026-01-14",
        }
    )
    assert score.played_on == date(2026, 1, 14)


def test_parse_box_score_rejects_invalid_us_dates():
    with pytest.raises(ValueError, match="invalid played_on date"):
        parse_box_score(
            {
                "home": "A",
                "away": "B",
                "home_score": 100,
                "away_score": 98,
                "played_on": "13/32/2026",
            }
        )
