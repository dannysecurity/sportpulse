from datetime import date
from pathlib import Path

import pytest

from sportpulse.parsers import (
    audit_box_scores,
    detect_box_score_format,
    import_box_scores_with_audit,
    load_box_scores,
    parse_box_scores_from_ndjson,
    parse_box_scores_text,
)


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_parse_ndjson_historical_export():
    text = """{"homeTeam":"A","awayTeam":"B","homeScore":101,"awayScore":99,"gameDate":"2026-01-10"}
{"homeTeam":"C","awayTeam":"D","homeScore":88,"awayScore":90}
"""
    scores = parse_box_scores_from_ndjson(text)
    assert len(scores) == 2
    assert scores[0].winner() == "A"
    assert scores[1].played_on is None


def test_parse_ndjson_skips_blank_lines():
    text = """
{"home":"A","away":"B","home_score":100,"away_score":98}

{"home":"C","away":"D","home_score":90,"away_score":88}
"""
    scores = parse_box_scores_from_ndjson(text)
    assert len(scores) == 2


def test_parse_ndjson_reports_invalid_json_line():
    text = '{"home":"A","away":"B","home_score":100,"away_score":98}\nnot-json\n'
    with pytest.raises(ValueError, match="NDJSON line 2: invalid JSON"):
        parse_box_scores_from_ndjson(text)


def test_parse_ndjson_reports_validation_errors_with_line_number():
    text = '{"home":"A","away":"B","home_score":100}\n'
    with pytest.raises(ValueError, match="NDJSON line 1: box score missing required field"):
        parse_box_scores_from_ndjson(text)


def test_detect_format_from_ndjson_content():
    text = """{"home":"A","away":"B","home_score":100,"away_score":98}
{"home":"C","away":"D","home_score":90,"away_score":88}
"""
    assert detect_box_score_format(text) == "ndjson"


def test_detect_format_from_json_array():
    text = '[{"home":"A","away":"B","home_score":100,"away_score":98}]'
    assert detect_box_score_format(text) == "json"


def test_detect_format_from_csv_header():
    text = "home,away,home_score,away_score\nA,B,100,98\n"
    assert detect_box_score_format(text) == "csv"


def test_detect_format_from_file_suffix():
    text = '{"home":"A","away":"B","home_score":100,"away_score":98}\n'
    assert detect_box_score_format(text, suffix="ndjson") == "ndjson"


def test_parse_box_scores_text_auto_detects_csv():
    text = "home,away,home_score,away_score\nA,B,100,98\n"
    scores, fmt = parse_box_scores_text(text)
    assert fmt == "csv"
    assert scores[0].home == "A"


def test_load_box_scores_from_ndjson_file(tmp_path: Path):
    path = tmp_path / "games.ndjson"
    path.write_text(
        '{"home":"A","away":"B","home_score":100,"away_score":98}\n',
        encoding="utf-8",
    )
    scores = load_box_scores(path)
    assert len(scores) == 1


def test_example_historical_export_ndjson_parses():
    scores = load_box_scores(EXAMPLES_DIR / "historical_export.ndjson")
    assert len(scores) == 4
    assert scores[0].home == "Lakers"


def test_audit_box_scores_summarizes_import():
    scores = load_box_scores(EXAMPLES_DIR / "historical_export.json")
    audit = audit_box_scores(scores, "json")
    assert audit.game_count == 4
    assert audit.format == "json"
    assert audit.first_played_on == date(2026, 1, 10)
    assert audit.last_played_on == date(2026, 1, 16)
    assert "Lakers" in audit.teams
    assert audit.duplicates == ()


def test_audit_box_scores_detects_duplicate_games():
    text = """home,away,home_score,away_score,played_on
A,B,100,98,2026-01-10
A,B,101,99,2026-01-10
"""
    scores, fmt = parse_box_scores_text(text, fmt="csv")
    audit = audit_box_scores(scores, fmt)
    assert len(audit.duplicates) == 1
    duplicate = audit.duplicates[0]
    assert duplicate.home == "A"
    assert duplicate.away == "B"
    assert duplicate.count == 2


def test_import_box_scores_with_audit_from_file():
    scores, audit = import_box_scores_with_audit(EXAMPLES_DIR / "historical_export.csv")
    assert len(scores) == 4
    assert audit.format == "csv"
    payload = audit.to_dict()
    assert payload["game_count"] == 4
    assert payload["date_range"]["first"] == "2026-01-10"
