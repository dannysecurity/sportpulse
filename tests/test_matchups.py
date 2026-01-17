from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.cli import main
from sportpulse.matchups import (
    build_matchups_report,
    load_matchups,
    matchups_for_date,
    project_matchup,
    ratings_from_history,
)
from sportpulse.parsers import load_box_scores

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_load_matchups_from_example():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")

    assert len(matchups) == 3
    assert matchups[0].home == "Celtics"
    assert matchups[0].scheduled_on == date(2026, 1, 16)


def test_matchups_for_date_filters_slate():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    slate = matchups_for_date(matchups, date(2026, 1, 16))

    assert len(slate) == 2
    assert {game.away for game in slate} == {"Knicks", "Heat"}


def test_ratings_from_history_uses_sample_season():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    ratings = ratings_from_history(scores)

    assert ratings["Lakers"] > 1500.0
    assert "Celtics" in ratings


def test_ratings_from_history_replays_games_chronologically():
    games = [
        BoxScore("Lakers", "Celtics", 112, 108, date(2026, 1, 10)),
        BoxScore("Warriors", "Lakers", 99, 102, date(2026, 1, 12)),
        BoxScore("Lakers", "Knicks", 105, 101, date(2026, 1, 14)),
    ]
    chronological = ratings_from_history(games)
    shuffled = ratings_from_history(list(reversed(games)))

    assert shuffled == chronological


def test_project_matchup_returns_probabilities():
    matchup = load_matchups(EXAMPLES_DIR / "matchups.json")[0]
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    ratings = ratings_from_history(scores)

    projection = project_matchup(matchup, ratings)

    assert projection["home"] == "Celtics"
    assert projection["away_win_prob"] == round(1.0 - projection["home_win_prob"], 3)
    assert 0.0 < projection["home_win_prob"] < 1.0


def test_build_matchups_report_for_date():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    assert report["date"] == "2026-01-16"
    assert len(report["matchups"]) == 2
    assert all("home_win_prob" in game for game in report["matchups"])


def test_cli_matchups_json(capsys):
    exit_code = main(
        [
            "matchups",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-16",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"date": "2026-01-16"' in output
    assert '"home_win_prob"' in output
