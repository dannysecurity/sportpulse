from datetime import date

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
