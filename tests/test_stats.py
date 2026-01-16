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


def test_point_differential_empty_games():
    assert point_differential("Lakers", []) == 0


def test_point_differential_losses_and_ties():
    games = [
        _game("Lakers", "Celtics", 80, 100),
        _game("Warriors", "Lakers", 110, 110),
        _game("Lakers", "Suns", 105, 95),
    ]
    assert point_differential("Lakers", games) == -10


def test_win_pct_all_wins_and_all_losses():
    wins_only = aggregate_record(
        "Lakers",
        [
            _game("Lakers", "Celtics", 110, 100),
            _game("Warriors", "Lakers", 95, 105),
        ],
    )
    losses_only = aggregate_record(
        "Lakers",
        [
            _game("Lakers", "Celtics", 90, 100),
            _game("Warriors", "Lakers", 110, 95),
        ],
    )
    assert wins_only.win_pct == pytest.approx(1.0)
    assert losses_only.win_pct == pytest.approx(0.0)


def test_games_in_range_empty_input():
    assert games_in_range([], date(2026, 1, 1), date(2026, 1, 31)) == []


def test_aggregate_record_in_range_all_undated_games():
    games = [
        _game("Lakers", "Celtics", 110, 105),
        _game("Warriors", "Lakers", 99, 102),
    ]
    record = aggregate_record_in_range(
        "Lakers",
        games,
        date(2026, 1, 1),
        date(2026, 1, 31),
    )
    assert record == TeamRecord()


def test_non_participant_in_tie_game_counts_as_tie():
    game = _game("Celtics", "Warriors", 100, 100)
    record = aggregate_record("Lakers", [game])
    assert record == TeamRecord(wins=0, losses=0, ties=1)


def test_team_record_addition_of_empty_records():
    empty = TeamRecord()
    combined = empty + empty
    assert combined == TeamRecord()
    assert combined.games_played == 0
    assert combined.win_pct == 0.0


def test_aggregate_record_vs_point_differential_non_participant_asymmetry():
    """Record counts non-participant games; point differential ignores them."""
    games = [
        _game("Celtics", "Warriors", 105, 99),
        _game("Lakers", "Celtics", 110, 100),
    ]
    record = aggregate_record("Lakers", games)
    assert record == TeamRecord(wins=1, losses=1, ties=0)
    assert point_differential("Lakers", games) == 10


def test_duplicate_games_double_count_in_record_and_point_diff():
    game = _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10))
    games = [game, game]
    record = aggregate_record("Lakers", games)
    assert record == TeamRecord(wins=2, losses=0, ties=0)
    assert record.games_played == 2
    assert point_differential("Lakers", games) == 20


def test_aggregate_record_in_range_matches_filtered_aggregate():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 120, 100, played_on=date(2026, 1, 12)),
        _game("Lakers", "Suns", 101, 99, played_on=date(2026, 2, 5)),
    ]
    start, end = date(2026, 1, 1), date(2026, 1, 31)
    ranged = aggregate_record_in_range("Lakers", games, start, end)
    filtered = aggregate_record("Lakers", games_in_range(games, start, end))
    assert ranged == filtered == TeamRecord(wins=1, losses=1, ties=0)


def test_team_record_addition_matches_split_monthly_aggregation():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
        _game("Lakers", "Suns", 98, 98, played_on=date(2026, 2, 5)),
        _game("Nuggets", "Lakers", 120, 100, played_on=date(2026, 2, 15)),
    ]
    january = aggregate_record_in_range(
        "Lakers", games, date(2026, 1, 1), date(2026, 1, 31)
    )
    february = aggregate_record_in_range(
        "Lakers", games, date(2026, 2, 1), date(2026, 2, 28)
    )
    full = aggregate_record("Lakers", games)
    assert january + february == full


def test_win_pct_with_wins_and_ties_only():
    record = aggregate_record(
        "Lakers",
        [
            _game("Lakers", "Celtics", 110, 100),
            _game("Warriors", "Lakers", 95, 95),
            _game("Lakers", "Suns", 105, 95),
        ],
    )
    assert record == TeamRecord(wins=2, losses=0, ties=1)
    assert record.games_played == 3
    assert record.win_pct == pytest.approx(2 / 3)


def test_games_in_range_single_day_window():
    target = date(2026, 1, 15)
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 14)),
        _game("Warriors", "Lakers", 99, 102, played_on=target),
        _game("Lakers", "Suns", 101, 99, played_on=date(2026, 1, 16)),
    ]
    filtered = games_in_range(games, target, target)
    assert filtered == [games[1]]
    record = aggregate_record_in_range("Lakers", games, target, target)
    assert record == TeamRecord(wins=1, losses=0, ties=0)


def test_aggregate_record_in_range_empty_when_start_after_end():
    games = [_game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10))]
    record = aggregate_record_in_range(
        "Lakers", games, date(2026, 2, 1), date(2026, 1, 1)
    )
    assert record == TeamRecord()


def test_aggregate_record_accepts_generator_iterable():
    def game_stream():
        yield _game("Lakers", "Celtics", 110, 100)
        yield _game("Warriors", "Lakers", 95, 105)

    record = aggregate_record("Lakers", game_stream())
    assert record == TeamRecord(wins=2, losses=0, ties=0)


def test_team_record_to_dict_non_empty():
    record = TeamRecord(wins=3, losses=1, ties=2)
    assert record.to_dict() == {"wins": 3, "losses": 1, "ties": 2}
    assert record.games_played == 6


def test_case_sensitive_team_name_does_not_match():
    games = [_game("Lakers", "Celtics", 110, 100)]
    record = aggregate_record("lakers", games)
    assert record == TeamRecord(wins=0, losses=1, ties=0)
    assert point_differential("lakers", games) == 0


def test_aggregate_record_in_range_only_out_of_window_dated_games():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2025, 12, 31)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 2, 1)),
    ]
    record = aggregate_record_in_range(
        "Lakers", games, date(2026, 1, 1), date(2026, 1, 31)
    )
    assert record == TeamRecord()
    assert record.win_pct == 0.0
