"""Edge-case tests for stat aggregation invariants and cross-layer consistency.

Exercises assertion helpers, partition math, self-match schedules, and
standings-layer date filtering against scenarios not covered by the core
stats and rollup edge-case suites.
"""

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
)
from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, aggregate_team_stats
from sportpulse.standings import (
    TeamStanding,
    VenueSplit,
    aggregate_standings,
    discover_teams,
    venue_split,
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


# --- assertion helper failure paths -------------------------------------------


def test_assert_mirror_records_raises_on_self_match():
    game = _game("Lakers", "Lakers", 110, 100)
    assert not check_mirror_records(game)
    with pytest.raises(AggregationInvariantError, match="Mirror record invariant failed"):
        assert_mirror_records(game)


def test_assert_league_point_diff_zero_sum_raises_on_self_match_league():
    """Self-match leagues have non-zero point-diff sum because only one team exists."""
    games = [_game("Lakers", "Lakers", 110, 100)]
    assert league_point_diff_sum(games) == 10
    assert not check_league_point_diff_zero_sum(games)
    with pytest.raises(AggregationInvariantError, match="League point-diff sum is 10"):
        assert_league_point_diff_zero_sum(games)


def test_assert_league_point_diff_zero_sum_raises_on_multi_self_match_league():
    """Each self-match adds positive PD with no opposing team to cancel it."""
    games = [
        _game("Lakers", "Lakers", 110, 100),
        _game("Celtics", "Celtics", 90, 85),
    ]
    assert league_point_diff_sum(games) == 15
    assert not check_league_point_diff_zero_sum(games)
    with pytest.raises(AggregationInvariantError, match="League point-diff sum is 15"):
        assert_league_point_diff_zero_sum(games)


# --- self-match cross-layer scenarios -----------------------------------------


def test_discover_teams_collapses_self_match_to_single_name():
    games = [_game("Lakers", "Lakers", 110, 100)]
    assert discover_teams(games) == frozenset({"Lakers"})


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param(ParticipationPolicy.PARTICIPANT_ONLY, id="participant_only"),
        pytest.param(ParticipationPolicy.COUNT_ALL, id="count_all"),
    ],
)
def test_self_match_standings_and_team_stats_agree(policy):
    games = [_game("Lakers", "Lakers", 110, 100, played_on=date(2026, 1, 10))]
    table = aggregate_standings(games, policy=policy)
    direct = aggregate_team_stats("Lakers", games, policy=policy)
    assert len(table) == 1
    assert table["Lakers"] == direct
    assert direct.record == TeamRecord(wins=1, losses=0, ties=0)
    assert direct.point_differential == 10


def test_self_match_venue_split_doubles_record_in_combined():
    """Home and away lists both include the same self-match game."""
    games = [_game("Lakers", "Lakers", 110, 100)]
    split = venue_split("Lakers", games)
    assert split.home == TeamRecord(wins=1, losses=0, ties=0)
    assert split.away == TeamRecord(wins=1, losses=0, ties=0)
    assert split.combined == TeamRecord(wins=2, losses=0, ties=0)
    assert isinstance(split, VenueSplit)


def test_self_match_league_invariants_do_not_hold():
    games = [_game("Lakers", "Lakers", 110, 100)]
    assert not check_league_point_diff_zero_sum(games)
    assert not check_mirror_records(games[0])


# --- partition edge cases -----------------------------------------------------


def test_partition_invariant_fails_when_ranges_overlap():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
    ]
    overlapping = [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 1, 15), date(2026, 1, 31)),
    ]
    result = partition_team_stats("Lakers", games, overlapping)
    assert not result.ok
    assert result.combined_record == TeamRecord(wins=3, losses=0, ties=0)
    assert result.full.record == TeamRecord(wins=2, losses=0, ties=0)
    with pytest.raises(AggregationInvariantError, match="Partition invariant failed"):
        assert_partition_invariant("Lakers", games, overlapping)


def test_partition_invariant_fails_when_ranges_empty():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
    ]
    result = partition_team_stats("Lakers", games, [])
    assert not result.ok
    assert result.combined_record == TeamRecord()
    assert result.full.record == TeamRecord(wins=2, losses=0, ties=0)
    with pytest.raises(AggregationInvariantError):
        assert_partition_invariant("Lakers", games, [])


def test_partition_invariant_detects_real_game_in_gap_under_count_all():
    games = [_game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10))]
    ranges = [
        (date(2026, 1, 1), date(2026, 1, 5)),
        (date(2026, 1, 16), date(2026, 1, 31)),
    ]
    result = partition_team_stats(
        "Lakers", games, ranges, policy=ParticipationPolicy.COUNT_ALL
    )
    assert not result.ok
    with pytest.raises(AggregationInvariantError):
        assert_partition_invariant(
            "Lakers", games, ranges, policy=ParticipationPolicy.COUNT_ALL
        )


def test_partition_invariant_detects_phantom_gap_under_count_all():
    """Phantom tie in a partition gap still breaks record reconciliation."""
    games = [
        _game("Celtics", "Warriors", 100, 100, played_on=date(2026, 1, 5)),
        _game("Lakers", "Suns", 105, 95, played_on=date(2026, 1, 15)),
        _game("Nuggets", "Heat", 110, 100, played_on=date(2026, 2, 10)),
    ]
    ranges = [
        (date(2026, 1, 1), date(2026, 1, 10)),
        (date(2026, 1, 20), date(2026, 1, 31)),
    ]
    result = partition_team_stats(
        "Lakers", games, ranges, policy=ParticipationPolicy.COUNT_ALL
    )
    assert not result.ok
    assert result.full.record == TeamRecord(wins=1, losses=1, ties=1)
    assert result.combined_record == TeamRecord(wins=0, losses=0, ties=1)


# --- standings partial date parameters ----------------------------------------


@pytest.mark.parametrize(
    "start,end",
    [
        pytest.param(date(2026, 1, 1), None, id="start_only"),
        pytest.param(None, date(2026, 1, 31), id="end_only"),
    ],
)
def test_aggregate_standings_partial_date_args_do_not_filter(start, end):
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 95, 105, played_on=date(2026, 2, 5)),
    ]
    full = aggregate_standings(games)
    partial = aggregate_standings(games, start=start, end=end)
    assert partial == full


def test_aggregate_standings_date_window_scopes_discovered_teams():
    """Teams with no dated games in the window are omitted from the table."""
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Suns", 99, 102, played_on=date(2026, 2, 5)),
    ]
    jan = aggregate_standings(
        games, start=date(2026, 1, 1), end=date(2026, 1, 31)
    )
    assert set(jan) == {"Lakers", "Celtics"}
    assert "Warriors" not in jan
    assert "Suns" not in jan


# --- policy alignment helpers -------------------------------------------------


def test_point_diff_counts_aligned_false_under_count_all_with_phantoms():
    games = [
        _game("Celtics", "Warriors", 100, 100),
        _game("Lakers", "Suns", 105, 95),
    ]
    stats = aggregate_team_stats("Lakers", games, policy=ParticipationPolicy.COUNT_ALL)
    assert not point_diff_counts_aligned(stats)
    assert count_all_point_diff_bounds(stats)


def test_point_diff_counts_aligned_true_when_record_and_diff_games_match():
    games = [_game("Lakers", "Suns", 105, 95)]
    stats = aggregate_team_stats("Lakers", games, policy=ParticipationPolicy.COUNT_ALL)
    assert point_diff_counts_aligned(stats)
    assert count_all_point_diff_bounds(stats)
    assert stats.games_in_record == stats.games_in_point_diff


def test_count_all_point_diff_bounds_holds_when_counts_equal():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105),
    ]
    stats = aggregate_team_stats(
        "Lakers", games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    count_all_stats = aggregate_team_stats(
        "Lakers", games, policy=ParticipationPolicy.COUNT_ALL
    )
    assert point_diff_counts_aligned(stats)
    assert point_diff_counts_aligned(count_all_stats)
    assert count_all_point_diff_bounds(count_all_stats)


# --- dataclass property accessors ---------------------------------------------


def test_team_standing_property_accessors():
    stats = aggregate_team_stats(
        "Lakers",
        [_game("Lakers", "Celtics", 110, 100)],
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
    )
    row = TeamStanding(team="Lakers", stats=stats)
    assert row.record == TeamRecord(wins=1, losses=0, ties=0)
    assert row.point_differential == 10
    assert row.win_pct == pytest.approx(1.0)
