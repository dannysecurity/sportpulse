from datetime import date

import pytest

from sportpulse.models import GameResult
from sportpulse.stats import (
    TeamRecord,
    aggregate_record,
    aggregate_record_in_range,
    games_in_range,
    point_differential,
)


def _game(
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    *,
    played_on: date | None = None,
) -> GameResult:
    return GameResult(home, away, home_score, away_score, played_on=played_on)


def test_empty_schedule_record():
    record = aggregate_record("Lakers", [])
    assert record == TeamRecord()
    assert record.games_played == 0
    assert record.win_pct == 0.0
    assert record.to_dict() == {"wins": 0, "losses": 0, "ties": 0}


def test_all_ties_including_zero_score():
    games = [
        _game("Lakers", "Celtics", 100, 100, played_on=date(2026, 1, 1)),
        _game("Warriors", "Lakers", 0, 0, played_on=date(2026, 1, 2)),
    ]
    record = aggregate_record("Lakers", games)
    assert record == TeamRecord(wins=0, losses=0, ties=2)
    assert record.win_pct == 0.0


def test_mixed_outcomes_and_home_away_split():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 12)),
        _game("Lakers", "Suns", 98, 98, played_on=date(2026, 1, 14)),
        _game("Nuggets", "Lakers", 120, 100, played_on=date(2026, 1, 16)),
    ]
    record = aggregate_record("Lakers", games)
    assert record == TeamRecord(wins=2, losses=1, ties=1)
    assert record.win_pct == pytest.approx(0.5)


def test_non_participant_counts_as_loss():
    game = _game("Celtics", "Warriors", 105, 99)
    record = aggregate_record("Lakers", [game])
    assert record == TeamRecord(wins=0, losses=1, ties=0)


def test_team_record_addition():
    first = TeamRecord(wins=3, losses=1, ties=0)
    second = TeamRecord(wins=1, losses=2, ties=1)
    assert first + second == TeamRecord(wins=4, losses=3, ties=1)


def test_games_in_range_excludes_undated_games():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102),
        _game("Lakers", "Suns", 101, 99, played_on=date(2026, 1, 20)),
    ]
    filtered = games_in_range(games, date(2026, 1, 1), date(2026, 1, 31))
    assert filtered == [games[0], games[2]]


def test_games_in_range_boundary_inclusive():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 1)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 31)),
    ]
    filtered = games_in_range(games, date(2026, 1, 1), date(2026, 1, 31))
    assert filtered == games


def test_games_in_range_empty_when_start_after_end():
    games = [_game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10))]
    assert games_in_range(games, date(2026, 2, 1), date(2026, 1, 1)) == []


def test_aggregate_record_in_range_ignores_out_of_window_games():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 120, 100, played_on=date(2026, 1, 12)),
        _game("Lakers", "Suns", 101, 99, played_on=date(2026, 2, 5)),
        _game("Nuggets", "Lakers", 98, 98, played_on=date(2026, 1, 15)),
    ]
    record = aggregate_record_in_range(
        "Lakers",
        games,
        date(2026, 1, 1),
        date(2026, 1, 31),
    )
    assert record == TeamRecord(wins=1, losses=1, ties=1)


def test_undated_games_count_in_full_record_but_not_in_range():
    games = [
        _game("Lakers", "Celtics", 110, 105),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 12)),
    ]
    full = aggregate_record("Lakers", games)
    ranged = aggregate_record_in_range(
        "Lakers",
        games,
        date(2026, 1, 1),
        date(2026, 1, 31),
    )
    assert full == TeamRecord(wins=2, losses=0, ties=0)
    assert ranged == TeamRecord(wins=1, losses=0, ties=0)


def test_point_differential_home_and_away():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105),
        _game("Celtics", "Warriors", 101, 99),
    ]
    assert point_differential("Lakers", games) == 20


def test_point_differential_zero_for_non_participant():
    games = [_game("Celtics", "Warriors", 105, 99)]
    assert point_differential("Lakers", games) == 0
