from datetime import date

import pytest

from sportpulse.models import GameResult
from sportpulse.schedule import Schedule


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
