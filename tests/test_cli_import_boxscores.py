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
