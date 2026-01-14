from datetime import date

from sportpulse.boxscore import BoxScore


def test_winner_and_summary():
    score = BoxScore(
        home="Lakers",
        away="Celtics",
        home_score=112,
        away_score=108,
        played_on=date(2026, 1, 14),
    )
    assert score.winner() == "Lakers"
    summary = score.summary()
    assert summary["margin"] == 4
    assert summary["played_on"] == "2026-01-14"


def test_tie_has_no_winner():
    score = BoxScore(home="A", away="B", home_score=100, away_score=100)
    assert score.winner() is None
