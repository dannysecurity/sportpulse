from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.cli import main
from sportpulse.parsers import load_box_scores
from sportpulse.ratings import (
    apply_game_to_ratings,
    build_batch_rating_update_report,
    build_rating_update_report,
    build_ratings_leaderboard,
    format_rating_update_table,
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


def test_build_rating_update_report_includes_pre_game_expectations():
    game = BoxScore("Lakers", "Celtics", 112, 108, date(2026, 2, 1))
    report = build_rating_update_report(game)

    home = report["updates"]["Lakers"]
    away = report["updates"]["Celtics"]
    assert home["expected"] == 0.5
    assert away["expected"] == 0.5
    assert round(home["expected"] + away["expected"], 3) == 1.0


def test_build_rating_update_report_expectations_reflect_home_advantage():
    game = BoxScore("Lakers", "Celtics", 112, 108, date(2026, 2, 1))
    report = build_rating_update_report(game, home_advantage=65.0)

    home = report["updates"]["Lakers"]
    away = report["updates"]["Celtics"]
    assert home["expected"] > 0.5
    assert away["expected"] < 0.5
    assert round(home["expected"] + away["expected"], 3) == 1.0


def test_build_rating_update_report_bootstraps_from_defaults():
    game = BoxScore("Lakers", "Celtics", 112, 108, date(2026, 2, 1))
    report = build_rating_update_report(game)

    assert report["games_replayed"] == 0
    assert report["updates"]["Lakers"]["before"] == 1500.0
    assert report["updates"]["Celtics"]["before"] == 1500.0
    assert report["updates"]["Lakers"]["after"] > report["updates"]["Lakers"]["before"]
    assert report["updates"]["Celtics"]["after"] < report["updates"]["Celtics"]["before"]
    assert (
        report["updates"]["Lakers"]["delta"] + report["updates"]["Celtics"]["delta"]
        == 0.0
    )


def test_build_rating_update_report_matches_full_replay():
    history = load_box_scores(EXAMPLES_DIR / "season.json")
    new_game = BoxScore("Lakers", "Celtics", 120, 100, date(2026, 2, 1))

    incremental = build_rating_update_report(
        new_game,
        history=history,
        include_leaderboard=True,
    )
    combined = build_ratings_leaderboard(history + [new_game])

    for team in ("Lakers", "Celtics"):
        assert incremental["updates"][team]["after"] == combined["ratings"][
            next(
                i
                for i, row in enumerate(combined["ratings"])
                if row["team"] == team
            )
        ]["rating"]

    assert incremental["games_replayed"] == 4
    assert len(incremental["ratings"]) == 5


def test_apply_game_to_ratings_respects_home_advantage():
    from sportpulse.elo import EloCalculator
    from sportpulse.models import EloRating

    game = BoxScore("Lakers", "Celtics", 105, 100, date(2026, 2, 1))
    neutral_ratings: dict[str, EloRating] = {}
    home_ratings: dict[str, EloRating] = {}

    neutral = apply_game_to_ratings(
        neutral_ratings,
        game,
        calculator=EloCalculator(k_factor=20.0, home_advantage=0.0),
    )
    with_home = apply_game_to_ratings(
        home_ratings,
        game,
        calculator=EloCalculator(k_factor=20.0, home_advantage=65.0),
    )

    assert with_home["Lakers"]["delta"] < neutral["Lakers"]["delta"]
    assert with_home["Celtics"]["delta"] > neutral["Celtics"]["delta"]


def test_cli_update_ratings_json(capsys):
    exit_code = main(
        [
            "update-ratings",
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--home",
            "Lakers",
            "--away",
            "Celtics",
            "--home-score",
            "120",
            "--away-score",
            "100",
            "--played-on",
            "2026-02-01",
            "--leaderboard",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"games_replayed": 4' in output
    assert '"before"' in output
    assert '"after"' in output
    assert '"played_on": "2026-02-01"' in output


def test_build_batch_rating_update_report_matches_full_replay():
    history = load_box_scores(EXAMPLES_DIR / "season.json")
    new_games = [
        BoxScore("Lakers", "Celtics", 120, 100, date(2026, 2, 1)),
        BoxScore("Warriors", "Heat", 110, 105, date(2026, 2, 2)),
    ]

    batch = build_batch_rating_update_report(
        new_games,
        history=history,
        include_leaderboard=True,
    )
    combined = build_ratings_leaderboard(history + new_games)

    assert batch["games_replayed"] == 4
    assert batch["games_applied"] == 2
    assert len(batch["game_updates"]) == 2
    for team in ("Lakers", "Celtics", "Warriors", "Heat"):
        assert batch["net_changes"][team]["after"] == combined["ratings"][
            next(
                i
                for i, row in enumerate(combined["ratings"])
                if row["team"] == team
            )
        ]["rating"]


def test_build_batch_rating_update_report_orders_undated_games_last():
    history = load_box_scores(EXAMPLES_DIR / "season.json")
    dated = BoxScore("Lakers", "Celtics", 120, 100, date(2026, 2, 3))
    undated = BoxScore("Warriors", "Heat", 110, 105)

    chronological = build_batch_rating_update_report(
        [dated, undated],
        history=history,
    )
    reversed_input = build_batch_rating_update_report(
        [undated, dated],
        history=history,
    )

    assert chronological["net_changes"] == reversed_input["net_changes"]


def test_format_rating_update_table_single_and_batch():
    history = load_box_scores(EXAMPLES_DIR / "season.json")
    single = build_rating_update_report(
        BoxScore("Lakers", "Celtics", 120, 100, date(2026, 2, 1)),
        history=history,
    )
    batch = build_batch_rating_update_report(
        [
            BoxScore("Lakers", "Celtics", 120, 100, date(2026, 2, 1)),
            BoxScore("Warriors", "Heat", 110, 105, date(2026, 2, 2)),
        ],
        history=history,
    )

    single_table = format_rating_update_table(single)
    batch_table = format_rating_update_table(batch)

    assert "ELO update" in single_table
    assert "Lakers" in single_table
    assert "BEFORE" in single_table
    assert "ELO batch update" in batch_table
    assert "Net change:" in batch_table
    assert "Game 1:" in batch_table
    assert "Game 2:" in batch_table


def test_cli_update_ratings_batch_table(capsys):
    exit_code = main(
        [
            "update-ratings",
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--games-file",
            str(EXAMPLES_DIR / "season.json"),
            "--output",
            "table",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "ELO batch update" in output
    assert "Net change:" in output


def test_cli_update_ratings_requires_game_or_file(capsys):
    exit_code = main(["update-ratings"])

    assert exit_code == 2
    assert "update-ratings:" in capsys.readouterr().err
