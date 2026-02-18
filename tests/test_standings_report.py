import json
from datetime import date
from pathlib import Path

from sportpulse.cli import main
from sportpulse.parsers import load_box_scores
from sportpulse.standings import build_standings_report, format_standings_table

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_build_standings_report_sample_season():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_standings_report(scores)

    assert report["games_counted"] == 4
    assert report["tie_breaker"] == "win_pct"
    standings = report["standings"]
    assert standings[0]["team"] == "Lakers"
    assert standings[0]["record"] == {"wins": 3, "losses": 0, "ties": 1}
    assert standings[0]["point_differential"] == 11
    assert len(standings) == 5


def test_build_standings_report_date_range():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_standings_report(
        scores,
        start=date(2026, 1, 11),
        end=date(2026, 1, 31),
    )

    assert report["start_date"] == "2026-01-11"
    assert report["end_date"] == "2026-01-31"
    assert report["games_counted"] == 3
    teams = [row["team"] for row in report["standings"]]
    assert "Celtics" not in teams
    assert report["standings"][0]["team"] == "Lakers"


def test_build_standings_report_from_csv_matches_json():
    json_report = build_standings_report(load_box_scores(EXAMPLES_DIR / "season.json"))
    csv_report = build_standings_report(load_box_scores(EXAMPLES_DIR / "season.csv"))
    assert json_report["standings"] == csv_report["standings"]


def test_format_standings_table_includes_header_and_lakers():
    report = build_standings_report(load_box_scores(EXAMPLES_DIR / "season.json"))
    table = format_standings_table(report)

    assert "League standings — 4 game(s)" in table
    assert "Lakers" in table
    assert "3-0-1" in table


def test_cli_standings_json(capsys):
    exit_code = main(
        [
            "standings",
            "--file",
            str(EXAMPLES_DIR / "season.json"),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["standings"][0]["team"] == "Lakers"


def test_cli_standings_table(capsys):
    exit_code = main(
        [
            "standings",
            "--file",
            str(EXAMPLES_DIR / "season.json"),
            "--output",
            "table",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "3-0-1" in output


def test_cli_standings_requires_both_dates(capsys):
    exit_code = main(
        [
            "standings",
            "--file",
            str(EXAMPLES_DIR / "season.json"),
            "--start-date",
            "2026-01-11",
        ]
    )

    assert exit_code == 2
    assert "both --start-date and --end-date" in capsys.readouterr().err
