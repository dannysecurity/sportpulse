from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.cli import main
from sportpulse.parsers import load_box_scores
from sportpulse.ratings import (
    build_ratings_leaderboard,
    format_ratings_table,
    rank_elo_ratings,
    replay_elo_ratings,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_replay_elo_ratings_replays_chronologically():
    games = [
        BoxScore("Lakers", "Celtics", 112, 108, date(2026, 1, 10)),
        BoxScore("Warriors", "Lakers", 99, 102, date(2026, 1, 12)),
        BoxScore("Lakers", "Knicks", 105, 101, date(2026, 1, 14)),
    ]
    chronological = replay_elo_ratings(games)
    shuffled = replay_elo_ratings(list(reversed(games)))

    assert chronological.ratings == shuffled.ratings
    assert chronological.games_replayed == 3


def test_build_ratings_leaderboard_ranks_lakers_first():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_ratings_leaderboard(scores)

    assert report["games_replayed"] == 4
    assert report["k_factor"] == 20.0
    ratings = report["ratings"]
    assert ratings[0]["team"] == "Lakers"
    assert ratings[0]["rank"] == 1
    assert ratings[0]["games_played"] == 4
    assert ratings[0]["delta"] == round(ratings[0]["rating"] - 1500.0, 1)
    teams = {row["team"] for row in ratings}
    assert teams == {"Lakers", "Celtics", "Warriors", "Knicks", "Heat"}


def test_rank_elo_ratings_breaks_ties_alphabetically():
    from sportpulse.models import EloRating

    ratings = {
        "Bulls": EloRating(team="Bulls", rating=1550.0, games_played=2),
        "Celtics": EloRating(team="Celtics", rating=1550.0, games_played=2),
        "Lakers": EloRating(team="Lakers", rating=1600.0, games_played=3),
    }
    ranked = rank_elo_ratings(ratings)

    assert [row["team"] for row in ranked] == ["Lakers", "Bulls", "Celtics"]
    assert ranked[1]["rank"] == 2
    assert ranked[2]["rank"] == 3


def test_format_ratings_table():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_ratings_leaderboard(scores)

    table = format_ratings_table(report)

    assert "ELO leaderboard" in table
    assert "Lakers" in table
    assert "RK" in table


def test_cli_ratings_json(capsys):
    exit_code = main(
        [
            "ratings",
            "--file",
            str(EXAMPLES_DIR / "season.json"),
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"games_replayed": 4' in output
    assert '"team": "Lakers"' in output


def test_cli_ratings_table(capsys):
    exit_code = main(
        [
            "ratings",
            "--file",
            str(EXAMPLES_DIR / "season.json"),
            "--output",
            "table",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "ELO leaderboard" in output
    assert "Lakers" in output
