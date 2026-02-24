import json
from pathlib import Path

from sportpulse.cli import main

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_cli_import_boxscores_json(capsys):
    exit_code = main(["import-boxscores", "--file", str(EXAMPLES_DIR / "season.json")])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 4
    assert payload[0]["home"] == "Lakers"


def test_cli_import_boxscores_historical_csv(capsys):
    exit_code = main(
        ["import-boxscores", "--file", str(EXAMPLES_DIR / "historical_export.csv")]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 4
    assert payload[1]["winner"] == "Lakers"


def test_cli_import_boxscores_audit(capsys):
    exit_code = main(
        [
            "import-boxscores",
            "--file",
            str(EXAMPLES_DIR / "historical_export.ndjson"),
            "--audit",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["games"]) == 4
    assert payload["audit"]["format"] == "ndjson"
    assert payload["audit"]["game_count"] == 4
    assert payload["audit"]["date_range"]["last"] == "2026-01-16"


def test_cli_import_boxscores_csv_output(capsys):
    exit_code = main(
        [
            "import-boxscores",
            "--file",
            str(EXAMPLES_DIR / "historical_export.csv"),
            "--output",
            "csv",
        ]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    lines = output.strip().splitlines()
    assert lines[0] == "home,away,home_score,away_score,played_on"
    assert len(lines) == 5
    assert lines[1].startswith("Lakers,Celtics,112,108,")


def test_cli_import_boxscores_csv_audit_writes_stderr(capsys):
    exit_code = main(
        [
            "import-boxscores",
            "--file",
            str(EXAMPLES_DIR / "historical_host_visitor.csv"),
            "--output",
            "csv",
            "--audit",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0] == "home,away,home_score,away_score,played_on"
    audit = json.loads(captured.err)
    assert audit["format"] == "csv"
    assert audit["game_count"] == 4
