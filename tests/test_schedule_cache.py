from datetime import date
from pathlib import Path

from sportpulse.schedule_cache import (
    clear_schedule_report_cache,
    file_fingerprint,
    load_matchups_report,
    load_season_report,
    load_standings_report,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_file_fingerprint_tracks_mtime_and_size(tmp_path: Path):
    path = tmp_path / "season.json"
    path.write_text("[]", encoding="utf-8")
    first = file_fingerprint(path)

    path.write_text('[{"home":"A","away":"B","home_score":1,"away_score":0}]', encoding="utf-8")
    second = file_fingerprint(path)

    assert first != second


def test_load_matchups_report_reuses_cache_until_file_changes(tmp_path: Path):
    clear_schedule_report_cache()
    matchups = tmp_path / "matchups.json"
    history = tmp_path / "season.json"
    matchups.write_text(
        '[{"home":"Celtics","away":"Knicks","scheduled_on":"2026-01-16"}]',
        encoding="utf-8",
    )
    history.write_text(
        '[{"home":"Celtics","away":"Knicks","home_score":110,"away_score":105,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )

    first = load_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history_file=history,
    )
    second = load_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history_file=history,
    )
    assert first is second

    matchups.write_text(
        '[{"home":"Lakers","away":"Heat","scheduled_on":"2026-01-16"}]',
        encoding="utf-8",
    )
    reloaded = load_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history_file=history,
    )
    assert reloaded is not first
    assert reloaded["matchups"][0]["home"] == "Lakers"


def test_load_matchups_report_cache_is_parameterized_by_date():
    clear_schedule_report_cache()
    matchups = EXAMPLES_DIR / "matchups.json"
    history = EXAMPLES_DIR / "season.json"

    day_one = load_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history_file=history,
    )
    day_two = load_matchups_report(
        matchups,
        on_date=date(2026, 1, 17),
        history_file=history,
    )

    assert day_one is not day_two
    assert day_one["date"] == "2026-01-16"
    assert day_two["date"] == "2026-01-17"


def test_load_season_report_reuses_cache_until_file_changes(tmp_path: Path):
    clear_schedule_report_cache()
    path = tmp_path / "season.json"
    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":110,"away_score":105,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )

    first = load_season_report(path, "Lakers")
    second = load_season_report(path, "Lakers")
    assert first is second

    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":99,"away_score":102,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )
    reloaded = load_season_report(path, "Lakers")
    assert reloaded is not first
    assert reloaded["record"] == {"wins": 0, "losses": 1, "ties": 0}


def test_load_standings_report_reuses_cache_until_file_changes(tmp_path: Path):
    clear_schedule_report_cache()
    path = tmp_path / "season.json"
    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":110,"away_score":105,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )

    first = load_standings_report(path)
    second = load_standings_report(path)
    assert first is second

    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":99,"away_score":102,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )
    reloaded = load_standings_report(path)
    assert reloaded is not first
    lakers = next(row for row in reloaded["standings"] if row["team"] == "Lakers")
    assert lakers["record"]["wins"] == 0


def test_load_season_report_matches_build_season_report(tmp_path: Path):
    clear_schedule_report_cache()
    source = EXAMPLES_DIR / "season.json"

    report = load_season_report(
        source,
        "Lakers",
        start=date(2026, 1, 11),
        end=date(2026, 1, 31),
    )

    assert report["team"] == "Lakers"
    assert report["games_played"] == 4
    assert report["record_in_range"] == {"wins": 2, "losses": 0, "ties": 1}
