from pathlib import Path

from sportpulse.parsers import load_box_scores


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_example_season_json_parses():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    assert len(scores) == 4
    assert scores[0].home == "Lakers"
    assert scores[0].played_on is not None


def test_example_season_csv_parses():
    scores = load_box_scores(EXAMPLES_DIR / "season.csv")
    assert len(scores) == 4
    assert scores[1].winner() == "Lakers"


def test_example_historical_export_json_parses():
    scores = load_box_scores(EXAMPLES_DIR / "historical_export.json")
    assert len(scores) == 4
    assert scores[0].home == "Lakers"
    assert scores[0].played_on is not None


def test_example_historical_export_csv_parses():
    scores = load_box_scores(EXAMPLES_DIR / "historical_export.csv")
    assert len(scores) == 4
    assert scores[2].winner() == "Lakers"


def test_example_historical_export_ndjson_parses():
    scores = load_box_scores(EXAMPLES_DIR / "historical_export.ndjson")
    assert len(scores) == 4
    assert scores[0].played_on is not None
