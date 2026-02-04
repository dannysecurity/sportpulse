"""Edge-case tests and invariant verification for stat aggregation."""

from datetime import date

import pytest

from sportpulse.aggregation_checks import (
    AggregationInvariantError,
    assert_league_point_diff_zero_sum,
    assert_mirror_records,
    assert_partition_invariant,
    check_league_point_diff_zero_sum,
    check_mirror_records,
    count_all_point_diff_bounds,
    league_point_diff_sum,
    partition_team_stats,
    point_diff_counts_aligned,
    single_game_records,
)
from sportpulse.models import GameResult
from sportpulse.rollup import (
    ParticipationPolicy,
    TeamStats,
    aggregate_team_stats,
    filter_participant_games,
)
from sportpulse.schedule import Schedule
from sportpulse.standings import (
    aggregate_standings,
    games_for_teams,
    head_to_head_record,
    rank_standings,
    standings_in_range,
)
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


# --- aggregation_checks module ------------------------------------------------


def test_partition_invariant_holds_for_participant_only_season():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
        _game("Lakers", "Suns", 98, 98, played_on=date(2026, 2, 5)),
    ]
    ranges = [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
    ]
    result = assert_partition_invariant("Lakers", games, ranges)
    assert result.ok
    assert result.full.record == TeamRecord(wins=2, losses=0, ties=1)


def test_partition_invariant_holds_under_count_all_with_phantom_games():
    """COUNT_ALL counts non-participant ties in record but not point diff."""
    games = [
        _game("Celtics", "Warriors", 100, 100, played_on=date(2026, 1, 5)),
        _game("Lakers", "Suns", 105, 95, played_on=date(2026, 1, 15)),
        _game("Nuggets", "Heat", 110, 100, played_on=date(2026, 2, 10)),
    ]
    ranges = [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
    ]
    result = assert_partition_invariant(
        "Lakers", games, ranges, policy=ParticipationPolicy.COUNT_ALL
    )
    assert result.ok
    assert result.full.record == TeamRecord(wins=1, losses=1, ties=1)
    assert result.full.point_differential == 10


def test_partition_invariant_detects_mismatch():
    games = [_game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10))]
    ranges = [
        (date(2026, 1, 1), date(2026, 1, 5)),
        (date(2026, 1, 16), date(2026, 1, 31)),
    ]
    result = partition_team_stats("Lakers", games, ranges)
    assert not result.ok
    assert result.combined_record == TeamRecord()
    assert result.full.record == TeamRecord(wins=1, losses=0, ties=0)
    with pytest.raises(AggregationInvariantError, match="Partition invariant failed"):
        assert_partition_invariant("Lakers", games, ranges)


@pytest.mark.parametrize(
    "game",
    [
        pytest.param(_game("Lakers", "Celtics", 110, 100), id="decided"),
        pytest.param(_game("Lakers", "Celtics", 100, 100), id="tie"),
        pytest.param(_game("Lakers", "Celtics", 0, 0), id="zero_score_tie"),
    ],
)
def test_mirror_records_hold_for_standard_games(game):
    assert check_mirror_records(game)
    assert_mirror_records(game)


def test_mirror_records_for_self_match():
    """Self-match games count as a single win for the duplicated team name."""
    game = _game("Lakers", "Lakers", 110, 100)
    home, away = single_game_records(game)
    assert home == away == TeamRecord(wins=1, losses=0, ties=0)
    assert not check_mirror_records(game)


def test_league_point_diff_zero_sum_round_robin():
    games = [
        _game("A", "B", 100, 90),
        _game("B", "C", 80, 85),
        _game("C", "A", 95, 95),
    ]
    assert check_league_point_diff_zero_sum(games)
    assert assert_league_point_diff_zero_sum(games) == 0


def test_league_point_diff_sum_respects_date_window():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Suns", 99, 102, played_on=date(2026, 2, 5)),
    ]
    assert league_point_diff_sum(
        games, start=date(2026, 1, 1), end=date(2026, 1, 31)
    ) == 0


def test_point_diff_counts_aligned_under_participant_only():
    games = [
        _game("Celtics", "Warriors", 100, 100),
        _game("Lakers", "Suns", 105, 95),
    ]
    stats = aggregate_team_stats(
        "Lakers", games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert point_diff_counts_aligned(stats)


def test_count_all_point_diff_bounds_when_phantom_games_present():
    games = [
        _game("Celtics", "Warriors", 100, 100),
        _game("Lakers", "Suns", 90, 90),
    ]
    stats = aggregate_team_stats("Lakers", games, policy=ParticipationPolicy.COUNT_ALL)
    assert count_all_point_diff_bounds(stats)
    assert stats.games_in_record == 2
    assert stats.games_in_point_diff == 1


# --- partial date parameters --------------------------------------------------


@pytest.mark.parametrize(
    "start,end",
    [
        pytest.param(date(2026, 1, 1), None, id="start_only"),
        pytest.param(None, date(2026, 1, 31), id="end_only"),
    ],
)
def test_partial_date_args_do_not_filter(start, end):
    """Date filtering requires both start and end; one-sided args are ignored."""
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 95, 105, played_on=date(2026, 2, 5)),
    ]
    full = aggregate_team_stats(
        "Lakers", games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    partial = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
        start=start,
        end=end,
    )
    assert partial == full


def test_aggregate_team_stats_empty_when_start_after_end():
    games = [_game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10))]
    stats = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
        start=date(2026, 2, 1),
        end=date(2026, 1, 1),
    )
    assert stats.record == TeamRecord()
    assert stats.point_differential == 0
    assert stats.games_in_record == 0


# --- head-to-head and self-match ----------------------------------------------


def test_head_to_head_same_team_returns_empty_record():
    games = [_game("Lakers", "Celtics", 110, 100)]
    assert head_to_head_record("Lakers", "Lakers", games) == TeamRecord()


def test_self_match_game_aggregation():
    game = _game("Lakers", "Lakers", 110, 100)
    stats = aggregate_team_stats(
        "Lakers", [game], policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert stats.record == TeamRecord(wins=1, losses=0, ties=0)
    assert stats.point_differential == 10
    assert stats.avg_margin == pytest.approx(10.0)


# --- helper coverage ----------------------------------------------------------


def test_filter_participant_games_direct():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Suns", 99, 102),
    ]
    assert filter_participant_games("Lakers", games) == [games[0]]
    assert filter_participant_games("Suns", games) == [games[1]]
    assert filter_participant_games("Nuggets", games) == []


def test_games_for_teams_case_sensitive():
    games = [_game("Lakers", "Celtics", 110, 100)]
    assert games_for_teams(games, ["Lakers"]) == games
    assert games_for_teams(games, ["lakers"]) == []
    assert games_for_teams(games, ["LAKERS"]) == []


def test_games_for_teams_whitespace_sensitive():
    games = [_game(" Lakers ", "Celtics", 110, 100)]
    assert games_for_teams(games, [" Lakers "]) == games
    assert games_for_teams(games, ["Lakers"]) == []


# --- avg_margin and serialization ---------------------------------------------


def test_avg_margin_under_count_all_with_mixed_participation():
    games = [
        _game("Celtics", "Warriors", 100, 100),
        _game("Lakers", "Suns", 120, 100),
    ]
    stats = aggregate_team_stats("Lakers", games, policy=ParticipationPolicy.COUNT_ALL)
    assert stats.record == TeamRecord(wins=1, losses=0, ties=1)
    assert stats.games_in_record == 2
    assert stats.games_in_point_diff == 1
    assert stats.point_differential == 20
    assert stats.avg_margin == pytest.approx(20.0)


def test_team_stats_to_dict_non_empty():
    stats = TeamStats(
        record=TeamRecord(wins=3, losses=1, ties=1),
        point_differential=42,
        games_in_record=5,
        games_in_point_diff=5,
    )
    assert stats.to_dict() == {
        "record": {"wins": 3, "losses": 1, "ties": 1},
        "point_differential": 42,
        "avg_margin": pytest.approx(8.4),
    }


# --- schedule integration -----------------------------------------------------


def test_schedule_record_matches_team_stats():
    sched = Schedule(team="Lakers")
    sched.add(_game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)))
    sched.add(_game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 12)))
    sched.add(_game("Lakers", "Suns", 98, 98, played_on=date(2026, 2, 5)))

    assert sched.record() == sched.team_stats().record.to_dict()
    assert sched.point_diff() == sched.team_stats().point_differential

    ranged = sched.team_stats(start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert sched.record_in_range(date(2026, 1, 1), date(2026, 1, 31)) == (
        ranged.record.to_dict()
    )


def test_schedule_between_excludes_out_of_range_and_undated():
    sched = Schedule(team="Lakers")
    sched.add(_game("Lakers", "Celtics", 110, 105))
    sched.add(_game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 12)))
    sched.add(_game("Lakers", "Suns", 101, 99, played_on=date(2026, 2, 5)))

    jan = sched.between(date(2026, 1, 1), date(2026, 1, 31))
    assert len(jan) == 1
    assert jan[0].played_on == date(2026, 1, 12)


# --- standings edge cases -----------------------------------------------------


def test_standings_undated_only_games_with_date_range_returns_empty():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Suns", 99, 102),
    ]
    assert standings_in_range(games, date(2026, 1, 1), date(2026, 1, 31)) == {}


def test_rank_standings_many_teams_tied_on_all_metrics():
    tied_stats = TeamStats(
        record=TeamRecord(wins=1, losses=1, ties=0),
        point_differential=0,
        games_in_record=2,
        games_in_point_diff=2,
    )
    standings = {name: tied_stats for name in ("Delta", "Alpha", "Charlie", "Bravo")}
    ranked = rank_standings(standings)
    assert [row.team for row in ranked] == ["Alpha", "Bravo", "Charlie", "Delta"]


def test_rank_standings_all_zero_records_sorts_alphabetically():
    zero = TeamStats(
        record=TeamRecord(),
        point_differential=0,
        games_in_record=0,
        games_in_point_diff=0,
    )
    standings = {"Zebra": zero, "Alpha": zero, "Mango": zero}
    ranked = rank_standings(standings, tie_breaker="team_name")
    assert [row.team for row in ranked] == ["Alpha", "Mango", "Zebra"]


def test_league_invariants_hold_on_example_season_slice():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 5)),
        _game("Celtics", "Warriors", 101, 99, played_on=date(2026, 1, 12)),
        _game("Warriors", "Lakers", 95, 105, played_on=date(2026, 1, 20)),
        _game("Lakers", "Warriors", 108, 108, played_on=date(2026, 2, 3)),
    ]
    assert assert_league_point_diff_zero_sum(games) == 0
    for game in games:
        assert_mirror_records(game)
    table = aggregate_standings(games)
    assert len(table) == 3
