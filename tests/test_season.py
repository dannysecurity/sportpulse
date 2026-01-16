from datetime import date
from pathlib import Path

from sportpulse.cli import main
from sportpulse.parsers import load_box_scores
from sportpulse.season import build_season_report

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_build_season_report_lakers_sample():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_season_report("Lakers", scores)

    assert report["team"] == "Lakers"
    assert report["games_played"] == 4
    assert report["record"] == {"wins": 3, "losses": 0, "ties": 1}
    assert "record_in_range" not in report
    assert isinstance(report["elo_rating"], float)
    assert len(report["elo_trend"]) == 5


def test_build_season_report_date_range():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_season_report(
        "Lakers",
        scores,
        start=date(2026, 1, 11),
        end=date(2026, 1, 31),
    )

    assert report["record_in_range"] == {"wins": 2, "losses": 0, "ties": 1}


def test_build_season_report_from_csv():
    scores = load_box_scores(EXAMPLES_DIR / "season.csv")
    report = build_season_report("Lakers", scores)

    assert report["games_played"] == 4
    assert report["record"] == {"wins": 3, "losses": 0, "ties": 1}


def test_cli_season_report_json(capsys):
    exit_code = main(
        [
            "season-report",
            "--team",
            "Lakers",
            "--file",
            str(EXAMPLES_DIR / "season.json"),
        ]
    )

    assert exit_code == 0
    payload = capsys.readouterr().out
    assert '"wins": 3' in payload
    assert '"ties": 1' in payload
    assert '"elo_trend"' in payload


def test_cli_season_report_requires_both_dates(capsys):
    exit_code = main(
        [
            "season-report",
            "--team",
            "Lakers",
            "--file",
            str(EXAMPLES_DIR / "season.json"),
            "--start-date",
            "2026-01-11",
        ]
    )

    assert exit_code == 2
    assert "both --start-date and --end-date" in capsys.readouterr().err
