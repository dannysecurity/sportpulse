"""Edge-case tests for stat aggregation reporting and league-level rollups.

Covers self-match ties, empty standings reports, malformed table rendering,
league-level partial date arguments, COUNT_ALL partition overlap, and mixed
undated/dated full-season aggregation — scenarios not exercised elsewhere.
"""

from datetime import date

import pytest

from sportpulse.aggregation_checks import (
    AggregationInvariantError,
    assert_league_point_diff_zero_sum,
    assert_participant_league_record_balanced,
    assert_partition_invariant,
    check_mirror_records,
    check_participant_league_record_balanced,
    league_point_diff_sum,
    league_record_totals,
    partition_team_stats,
)
from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, aggregate_team_stats
from sportpulse.standings import (
    aggregate_standings,
    build_standings_report,
    discover_teams,
    format_standings_table,
    head_to_head_record,
    venue_split,
)
from sportpulse.stats import (
    TeamRecord,
    games_in_range,
    point_differential,
    point_differential_in_range,
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


# --- self-match ties ----------------------------------------------------------


def test_self_match_tie_records_one_tie_per_side():
    game = _game("Lakers", "Lakers", 100, 100)
    stats = aggregate_team_stats(
        "Lakers", [game], policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert stats.record == TeamRecord(wins=0, losses=0, ties=1)
    assert stats.point_differential == 0
    assert check_mirror_records(game)


def test_self_match_tie_venue_split_doubles_ties_in_combined():
    games = [_game("Lakers", "Lakers", 100, 100)]
    split = venue_split("Lakers", games)
    assert split.home == TeamRecord(wins=0, losses=0, ties=1)
    assert split.away == TeamRecord(wins=0, losses=0, ties=1)
    assert split.combined == TeamRecord(wins=0, losses=0, ties=2)


def test_self_match_tie_league_record_balance_still_holds():
    """Self-match tie counts once in league totals; wins still equal losses."""
    games = [_game("Lakers", "Lakers", 100, 100)]
    totals = league_record_totals(games)
    assert totals == TeamRecord(wins=0, losses=0, ties=1)
    assert check_participant_league_record_balanced(games)
    assert assert_league_point_diff_zero_sum(games) == 0


# --- empty and malformed reporting --------------------------------------------


def test_build_standings_report_empty_input():
    report = build_standings_report([])
    assert report["games_counted"] == 0
    assert report["tie_breaker"] == "win_pct"
    assert report["standings"] == []


def test_format_standings_table_empty_standings():
    table = format_standings_table({"games_counted": 0, "standings": []})
    assert table == "League standings — 0 game(s)\n\nNo games to rank."


def test_format_standings_table_rejects_non_list_standings():
    with pytest.raises(ValueError, match="report standings must be a list"):
        format_standings_table({"standings": "invalid"})


def test_format_standings_table_skips_malformed_rows():
    report = {
        "games_counted": 1,
        "standings": [
            "not-a-row",
            {"rank": 1, "team": "Lakers", "record": "bad", "win_pct": 1.0},
            {
                "rank": 1,
                "team": "Lakers",
                "record": {"wins": 3, "losses": 0, "ties": 1},
                "win_pct": 1.0,
                "point_differential": 11,
                "avg_margin": 2.8,
            },
        ],
    }
    table = format_standings_table(report)
    assert "Lakers" in table
    assert "3-0-1" in table
    assert table.count("Lakers") == 1


# --- league-level partial date arguments --------------------------------------


@pytest.mark.parametrize(
    "start,end",
    [
        pytest.param(date(2026, 1, 1), None, id="start_only"),
        pytest.param(None, date(2026, 1, 31), id="end_only"),
    ],
)
def test_league_record_totals_partial_date_args_do_not_filter(start, end):
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 95, 105, played_on=date(2026, 2, 5)),
    ]
    full = league_record_totals(games)
    partial = league_record_totals(games, start=start, end=end)
    assert partial == full == TeamRecord(wins=2, losses=2, ties=0)


@pytest.mark.parametrize(
    "start,end",
    [
        pytest.param(date(2026, 1, 1), None, id="start_only"),
        pytest.param(None, date(2026, 1, 31), id="end_only"),
    ],
)
def test_league_point_diff_sum_partial_date_args_do_not_filter(start, end):
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 95, 105, played_on=date(2026, 2, 5)),
    ]
    full = league_point_diff_sum(games)
    partial = league_point_diff_sum(games, start=start, end=end)
    assert partial == full == 0


# --- point_differential_in_range direct coverage ------------------------------


def test_point_differential_in_range_excludes_undated_games():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 120, 100, played_on=date(2026, 1, 12)),
    ]
    start, end = date(2026, 1, 1), date(2026, 1, 31)
    assert point_differential_in_range("Lakers", games, start, end) == -20
    filtered = point_differential("Lakers", games_in_range(games, start, end))
    assert point_differential_in_range("Lakers", games, start, end) == filtered


def test_point_differential_in_range_zero_when_all_games_undated():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105),
    ]
    assert point_differential_in_range(
        "Lakers", games, date(2026, 1, 1), date(2026, 1, 31)
    ) == 0


# --- mixed undated and dated full-season rollups ------------------------------


def test_full_season_includes_undated_and_dated_games():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105, played_on=date(2026, 1, 12)),
    ]
    standings = aggregate_standings(games)
    assert discover_teams(games) == frozenset({"Lakers", "Celtics", "Warriors"})
    assert standings["Lakers"].record == TeamRecord(wins=2, losses=0, ties=0)
    assert standings["Lakers"].point_differential == 20


def test_date_window_excludes_undated_but_full_season_keeps_them():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105, played_on=date(2026, 1, 12)),
    ]
    jan = aggregate_standings(
        games, start=date(2026, 1, 1), end=date(2026, 1, 31)
    )
    full = aggregate_standings(games)
    assert jan["Lakers"].record == TeamRecord(wins=1, losses=0, ties=0)
    assert full["Lakers"].record == TeamRecord(wins=2, losses=0, ties=0)


# --- COUNT_ALL league and partition edge cases --------------------------------


def test_count_all_overlapping_partitions_break_invariant():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
    ]
    overlapping = [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 1, 15), date(2026, 1, 31)),
    ]
    result = partition_team_stats(
        "Lakers", games, overlapping, policy=ParticipationPolicy.COUNT_ALL
    )
    assert not result.ok
    with pytest.raises(AggregationInvariantError, match="Partition invariant failed"):
        assert_partition_invariant(
            "Lakers", games, overlapping, policy=ParticipationPolicy.COUNT_ALL
        )


def test_count_all_three_team_league_phantom_balance_raises():
    """Every team sees phantom ties from games they did not play."""
    games = [
        _game("A", "B", 100, 100, played_on=date(2026, 1, 5)),
        _game("B", "C", 105, 95, played_on=date(2026, 1, 10)),
        _game("C", "A", 90, 90, played_on=date(2026, 1, 15)),
    ]
    assert not check_participant_league_record_balanced(
        games, policy=ParticipationPolicy.COUNT_ALL
    )
    with pytest.raises(AggregationInvariantError, match="League record balance failed"):
        assert_participant_league_record_balanced(
            games, policy=ParticipationPolicy.COUNT_ALL
        )


def test_count_all_phantom_games_preserve_league_point_diff_zero_sum():
    games = [
        _game("Celtics", "Warriors", 100, 100, played_on=date(2026, 1, 5)),
        _game("Lakers", "Suns", 105, 95, played_on=date(2026, 1, 15)),
    ]
    assert assert_league_point_diff_zero_sum(
        games, policy=ParticipationPolicy.COUNT_ALL
    ) == 0


# --- partition result accessors and head-to-head with self-match --------------


def test_partition_result_property_accessors():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
    ]
    ranges = [
        (date(2026, 1, 1), date(2026, 1, 15)),
        (date(2026, 1, 16), date(2026, 1, 31)),
    ]
    result = partition_team_stats("Lakers", games, ranges)
    assert result.record_matches
    assert result.point_diff_matches
    assert result.ok
    assert result.combined_record == result.full.record
    assert result.combined_point_diff == result.full.point_differential


def test_head_to_head_ignores_self_match_on_same_schedule():
    games = [
        _game("Lakers", "Lakers", 110, 100, played_on=date(2026, 1, 5)),
        _game("Lakers", "Celtics", 105, 99, played_on=date(2026, 1, 12)),
        _game("Celtics", "Lakers", 102, 98, played_on=date(2026, 1, 20)),
    ]
    assert head_to_head_record("Lakers", "Celtics", games) == TeamRecord(
        wins=1, losses=1, ties=0
    )
    assert head_to_head_record("Lakers", "Lakers", games) == TeamRecord()
