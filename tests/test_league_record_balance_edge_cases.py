"""Edge-case tests for league-wide record aggregation balance invariants.

Each standard game contributes one win and one loss (or one tie per
participant). Summing records across teams should reconcile unless
self-matches or COUNT_ALL phantom outcomes distort the totals.
"""

from datetime import date

import pytest

from sportpulse.aggregation_checks import (
    AggregationInvariantError,
    assert_participant_league_record_balanced,
    check_participant_league_record_balanced,
    league_record_totals,
)
from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy
from sportpulse.stats import TeamRecord


def _game(
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    *,
    played_on: date | None = None,
) -> GameResult:
    return GameResult(home, away, home_score, away_score, played_on=played_on)


def test_league_record_totals_empty_schedule():
    totals = league_record_totals([])
    assert totals == TeamRecord()
    assert check_participant_league_record_balanced([])


def test_league_record_totals_single_decided_game():
    games = [_game("Lakers", "Celtics", 110, 100)]
    totals = league_record_totals(games)
    assert totals == TeamRecord(wins=1, losses=1, ties=0)
    assert assert_participant_league_record_balanced(games) == totals


def test_league_record_totals_single_tie():
    games = [_game("Lakers", "Celtics", 100, 100)]
    totals = league_record_totals(games)
    assert totals == TeamRecord(wins=0, losses=0, ties=2)
    assert check_participant_league_record_balanced(games)


def test_league_record_totals_three_team_round_robin():
    games = [
        _game("A", "B", 100, 90),
        _game("B", "C", 80, 85),
        _game("C", "A", 95, 95),
    ]
    totals = league_record_totals(games)
    assert totals.wins == totals.losses == 2
    assert totals.ties == 2
    assert_participant_league_record_balanced(games)


def test_league_record_totals_all_ties_league():
    games = [
        _game("A", "B", 50, 50),
        _game("C", "D", 0, 0),
    ]
    totals = league_record_totals(games)
    assert totals == TeamRecord(wins=0, losses=0, ties=4)
    assert check_participant_league_record_balanced(games)


def test_league_record_totals_respects_date_window():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Suns", 99, 102, played_on=date(2026, 2, 5)),
    ]
    jan_totals = league_record_totals(
        games, start=date(2026, 1, 1), end=date(2026, 1, 31)
    )
    assert jan_totals == TeamRecord(wins=1, losses=1, ties=0)
    assert check_participant_league_record_balanced(
        games, start=date(2026, 1, 1), end=date(2026, 1, 31)
    )


def test_league_record_totals_empty_when_window_has_no_dated_games():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Suns", 99, 102),
    ]
    totals = league_record_totals(
        games, start=date(2026, 1, 1), end=date(2026, 1, 31)
    )
    assert totals == TeamRecord()
    assert check_participant_league_record_balanced(
        games, start=date(2026, 1, 1), end=date(2026, 1, 31)
    )


def test_league_record_totals_empty_when_start_after_end():
    games = [_game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10))]
    totals = league_record_totals(
        games, start=date(2026, 2, 1), end=date(2026, 1, 1)
    )
    assert totals == TeamRecord()
    assert check_participant_league_record_balanced(
        games, start=date(2026, 2, 1), end=date(2026, 1, 1)
    )


def test_self_match_breaks_league_record_balance():
    games = [_game("Lakers", "Lakers", 110, 100)]
    totals = league_record_totals(games)
    assert totals == TeamRecord(wins=1, losses=0, ties=0)
    assert not check_participant_league_record_balanced(games)
    with pytest.raises(
        AggregationInvariantError, match="League record balance failed"
    ):
        assert_participant_league_record_balanced(games)


def test_multiple_self_matches_accumulate_imbalance():
    games = [
        _game("Lakers", "Lakers", 110, 100),
        _game("Celtics", "Celtics", 90, 85),
    ]
    totals = league_record_totals(games)
    assert totals == TeamRecord(wins=2, losses=0, ties=0)
    assert not check_participant_league_record_balanced(games)
    with pytest.raises(AggregationInvariantError, match="2 wins != 0 losses"):
        assert_participant_league_record_balanced(games)


def test_count_all_phantom_outcomes_break_league_balance():
    """Non-participant COUNT_ALL outcomes inflate losses without matching wins."""
    games = [
        _game("Celtics", "Warriors", 100, 100, played_on=date(2026, 1, 5)),
        _game("Lakers", "Suns", 105, 95, played_on=date(2026, 1, 15)),
    ]
    participant_totals = league_record_totals(
        games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    count_all_totals = league_record_totals(
        games, policy=ParticipationPolicy.COUNT_ALL
    )
    assert participant_totals == TeamRecord(wins=1, losses=1, ties=2)
    assert check_participant_league_record_balanced(
        games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert count_all_totals == TeamRecord(wins=1, losses=3, ties=4)
    assert not check_participant_league_record_balanced(
        games, policy=ParticipationPolicy.COUNT_ALL
    )


def test_duplicate_games_double_count_league_totals():
    game = _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10))
    games = [game, game]
    totals = league_record_totals(games)
    assert totals == TeamRecord(wins=2, losses=2, ties=0)
    assert check_participant_league_record_balanced(games)


def test_mixed_decided_and_tied_games_remain_balanced():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 5)),
        _game("Warriors", "Suns", 98, 98, played_on=date(2026, 1, 12)),
        _game("Celtics", "Warriors", 101, 99, played_on=date(2026, 1, 20)),
    ]
    totals = league_record_totals(games)
    assert totals.wins == totals.losses == 2
    assert totals.ties == 2
    assert_participant_league_record_balanced(games)


def test_league_record_totals_accepts_generator_input():
    games = [
        _game("A", "B", 100, 90),
        _game("B", "A", 85, 95),
    ]

    def game_stream():
        yield from games

    totals = league_record_totals(game_stream())
    assert totals == TeamRecord(wins=2, losses=2, ties=0)
    assert check_participant_league_record_balanced(games)
