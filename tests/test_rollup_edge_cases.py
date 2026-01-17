"""Edge-case tests for stat rollup policies and unified aggregation."""

from datetime import date

import pytest

from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, TeamStats, aggregate_team_stats
from sportpulse.stats import (
    TeamRecord,
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


@pytest.mark.parametrize(
    ("policy", "expected_record", "expected_pd", "expected_pd_games"),
    [
        pytest.param(
            ParticipationPolicy.COUNT_ALL,
            TeamRecord(wins=0, losses=1, ties=0),
            0,
            0,
            id="count_all_non_participant_loss",
        ),
        pytest.param(
            ParticipationPolicy.PARTICIPANT_ONLY,
            TeamRecord(),
            0,
            0,
            id="participant_only_non_participant_loss",
        ),
    ],
)
def test_non_participant_decided_game_by_policy(
    policy, expected_record, expected_pd, expected_pd_games
):
    games = [_game("Celtics", "Warriors", 105, 99)]
    stats = aggregate_team_stats("Lakers", games, policy=policy)
    assert stats.record == expected_record
    assert stats.point_differential == expected_pd
    assert stats.games_in_point_diff == expected_pd_games


@pytest.mark.parametrize(
    ("policy", "expected_record", "expected_pd_games"),
    [
        pytest.param(
            ParticipationPolicy.COUNT_ALL,
            TeamRecord(wins=0, losses=0, ties=1),
            0,
            id="count_all_non_participant_tie",
        ),
        pytest.param(
            ParticipationPolicy.PARTICIPANT_ONLY,
            TeamRecord(),
            0,
            id="participant_only_non_participant_tie",
        ),
    ],
)
def test_non_participant_tie_game_by_policy(policy, expected_record, expected_pd_games):
    games = [_game("Celtics", "Warriors", 100, 100)]
    stats = aggregate_team_stats("Lakers", games, policy=policy)
    assert stats.record == expected_record
    assert stats.point_differential == 0
    assert stats.games_in_point_diff == expected_pd_games


def test_participant_only_aligns_record_and_point_diff_counts():
    games = [
        _game("Celtics", "Warriors", 105, 99),
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 95),
    ]
    stats = aggregate_team_stats(
        "Lakers", games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert stats.games_in_record == stats.games_in_point_diff == 2
    assert stats.record == TeamRecord(wins=1, losses=0, ties=1)
    assert stats.point_differential == 10
    assert stats.avg_margin == pytest.approx(5.0)


def test_count_all_keeps_record_point_diff_asymmetry():
    games = [
        _game("Celtics", "Warriors", 100, 100),
        _game("Lakers", "Suns", 90, 90),
    ]
    stats = aggregate_team_stats("Lakers", games, policy=ParticipationPolicy.COUNT_ALL)
    assert stats.record == TeamRecord(wins=0, losses=0, ties=2)
    assert stats.games_in_record == 2
    assert stats.point_differential == 0
    assert stats.games_in_point_diff == 1


def test_range_filter_excludes_undated_games_from_both_rollups():
    games = [
        _game("Lakers", "Celtics", 110, 105),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 12)),
    ]
    stats = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
    )
    assert stats.record == TeamRecord(wins=1, losses=0, ties=0)
    assert stats.point_differential == 3
    assert stats.games_in_record == 1


def test_range_with_non_participant_game_inside_window():
    games = [
        _game("Celtics", "Warriors", 100, 100, played_on=date(2026, 1, 15)),
        _game("Lakers", "Suns", 105, 95, played_on=date(2026, 1, 20)),
    ]
    count_all = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.COUNT_ALL,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
    )
    participant_only = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
    )
    assert count_all.record == TeamRecord(wins=1, losses=0, ties=1)
    assert count_all.point_differential == 10
    assert participant_only.record == TeamRecord(wins=1, losses=0, ties=0)
    assert participant_only.point_differential == 10
    assert participant_only.games_in_record == participant_only.games_in_point_diff


def test_point_differential_in_range_matches_filtered_point_diff():
    games = [
        _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 120, 100, played_on=date(2026, 1, 12)),
        _game("Lakers", "Suns", 101, 99, played_on=date(2026, 2, 5)),
    ]
    start, end = date(2026, 1, 1), date(2026, 1, 31)
    ranged = point_differential_in_range("Lakers", games, start, end)
    participant_stats = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
        start=start,
        end=end,
    )
    assert ranged == participant_stats.point_differential == -10


def test_monthly_partition_invariant_under_participant_only():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
        _game("Lakers", "Suns", 98, 98, played_on=date(2026, 2, 5)),
        _game("Nuggets", "Lakers", 120, 100, played_on=date(2026, 2, 15)),
    ]
    january = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
    )
    february = aggregate_team_stats(
        "Lakers",
        games,
        policy=ParticipationPolicy.PARTICIPANT_ONLY,
        start=date(2026, 2, 1),
        end=date(2026, 2, 28),
    )
    full = aggregate_team_stats(
        "Lakers", games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert january.record + february.record == full.record
    assert (
        january.point_differential + february.point_differential
        == full.point_differential
    )


def test_duplicate_games_double_count_under_both_policies():
    game = _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10))
    games = [game, game]
    for policy in ParticipationPolicy:
        stats = aggregate_team_stats("Lakers", games, policy=policy)
        assert stats.record == TeamRecord(wins=2, losses=0, ties=0)
        assert stats.point_differential == 20
        assert stats.games_in_record == 2


def test_empty_input_returns_zeroed_team_stats():
    stats = aggregate_team_stats("Lakers", [], policy=ParticipationPolicy.PARTICIPANT_ONLY)
    assert stats == TeamStats(
        record=TeamRecord(),
        point_differential=0,
        games_in_record=0,
        games_in_point_diff=0,
    )
    assert stats.avg_margin == 0.0
    assert stats.to_dict() == {
        "record": {"wins": 0, "losses": 0, "ties": 0},
        "point_differential": 0,
        "avg_margin": 0.0,
    }


def test_case_sensitive_team_name_affects_both_rollups():
    games = [_game("Lakers", "Celtics", 110, 100)]
    stats = aggregate_team_stats("lakers", games, policy=ParticipationPolicy.COUNT_ALL)
    assert stats.record == TeamRecord(wins=0, losses=1, ties=0)
    assert stats.point_differential == 0
    assert stats.games_in_point_diff == 0


def test_negative_scores_still_aggregate():
    games = [_game("Lakers", "Celtics", -5, -10)]
    stats = aggregate_team_stats("Lakers", games, policy=ParticipationPolicy.PARTICIPANT_ONLY)
    assert stats.record == TeamRecord(wins=1, losses=0, ties=0)
    assert stats.point_differential == 5


def test_whitespace_team_name_does_not_match():
    games = [_game(" Lakers ", "Celtics", 110, 100)]
    stats = aggregate_team_stats("Lakers", games, policy=ParticipationPolicy.PARTICIPANT_ONLY)
    assert stats.record == TeamRecord()
    assert stats.point_differential == 0


def test_point_differential_in_range_empty_when_start_after_end():
    games = [_game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10))]
    assert point_differential_in_range(
        "Lakers", games, date(2026, 2, 1), date(2026, 1, 1)
    ) == 0


def test_game_result_involves():
    game = _game("Lakers", "Celtics", 110, 100)
    assert game.involves("Lakers")
    assert game.involves("Celtics")
    assert not game.involves("Warriors")


def test_generator_input_supported():
    def game_stream():
        yield _game("Lakers", "Celtics", 110, 100)
        yield _game("Warriors", "Lakers", 95, 105)

    stats = aggregate_team_stats(
        "Lakers", game_stream(), policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert stats.record == TeamRecord(wins=2, losses=0, ties=0)
    assert stats.point_differential == 20
