from datetime import date
from pathlib import Path

import pytest

from sportpulse.models import GameResult
import sportpulse.schedule as schedule_module
from sportpulse.schedule import Schedule, clear_schedule_cache, load_team_schedule

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_schedule_record_and_filter():
    sched = Schedule(team="Lakers")
    sched.add(
        GameResult("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10))
    )
    sched.add(
        GameResult("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 12))
    )

    assert sched.record() == {"wins": 2, "losses": 0, "ties": 0}

    jan_games = sched.between(date(2026, 1, 1), date(2026, 1, 31))
    assert len(jan_games) == 2

    assert sched.record_in_range(date(2026, 1, 11), date(2026, 1, 31)) == {
        "wins": 1,
        "losses": 0,
        "ties": 0,
    }


def test_schedule_add_rejects_non_participant():
    sched = Schedule(team="Lakers")
    with pytest.raises(ValueError, match="Lakers is not a participant"):
        sched.add(GameResult("Celtics", "Warriors", 105, 99))


def test_load_team_schedule_from_example():
    schedule = load_team_schedule(EXAMPLES_DIR / "season.json", "Lakers")

    assert schedule.team == "Lakers"
    assert schedule.record() == {"wins": 3, "losses": 0, "ties": 1}


def test_load_team_schedule_reuses_cache_until_file_changes(tmp_path: Path):
    clear_schedule_cache()
    path = tmp_path / "season.json"
    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":110,"away_score":105,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )

    first = load_team_schedule(path, "Lakers")
    second = load_team_schedule(path, "Lakers")
    assert first is second

    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":99,"away_score":102,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )
    reloaded = load_team_schedule(path, "Lakers")
    assert reloaded is not first
    assert reloaded.record() == {"wins": 0, "losses": 1, "ties": 0}


def test_load_team_schedule_cache_is_parameterized_by_fmt(tmp_path: Path):
    clear_schedule_cache()
    path = tmp_path / "season.json"
    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":110,"away_score":105,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )

    load_team_schedule(path, "Lakers", fmt="json")
    load_team_schedule(path, "Lakers", fmt=None)

    assert len(schedule_module._schedule_cache) == 2


def test_load_team_schedule_cache_is_per_team(tmp_path: Path):
    clear_schedule_cache()
    path = tmp_path / "season.json"
    path.write_text(
        '[{"home":"Lakers","away":"Celtics","home_score":110,"away_score":105,'
        '"played_on":"2026-01-10"}]',
        encoding="utf-8",
    )

    lakers = load_team_schedule(path, "Lakers")
    celtics = load_team_schedule(path, "Celtics")
    assert lakers is not celtics
    assert lakers.record() == {"wins": 1, "losses": 0, "ties": 0}
    assert celtics.record() == {"wins": 0, "losses": 1, "ties": 0}
