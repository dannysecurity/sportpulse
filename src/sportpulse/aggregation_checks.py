"""Invariant verification for stat aggregation rollups.

SportPulse rollups obey several structural properties: monthly partitions
should reconcile to season totals, league-wide point differentials should sum
to zero, and mirror records between opponents should always balance. These
helpers encode those properties for use in tests, data-import validation,
and debugging aggregation pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, TeamStats, aggregate_team_stats
from sportpulse.standings import aggregate_standings
from sportpulse.stats import TeamRecord, aggregate_record


class AggregationInvariantError(Exception):
    """Raised when an aggregation invariant check fails."""


@dataclass(frozen=True)
class PartitionResult:
    """Comparison of partitioned rollups against a full-window aggregate."""

    full: TeamStats
    parts: tuple[TeamStats, ...]
    combined_record: TeamRecord
    combined_point_diff: int

    @property
    def record_matches(self) -> bool:
        return self.combined_record == self.full.record

    @property
    def point_diff_matches(self) -> bool:
        return self.combined_point_diff == self.full.point_differential

    @property
    def ok(self) -> bool:
        return self.record_matches and self.point_diff_matches


def partition_team_stats(
    team: str,
    games: Iterable[GameResult],
    ranges: Sequence[tuple[date, date]],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
) -> PartitionResult:
    """Roll up stats per date range and compare against the full schedule."""
    game_list = list(games)
    full = aggregate_team_stats(team, game_list, policy=policy)
    parts = tuple(
        aggregate_team_stats(
            team,
            game_list,
            policy=policy,
            start=start,
            end=end,
        )
        for start, end in ranges
    )
    combined_record = sum((part.record for part in parts), TeamRecord())
    combined_point_diff = sum(part.point_differential for part in parts)
    return PartitionResult(
        full=full,
        parts=parts,
        combined_record=combined_record,
        combined_point_diff=combined_point_diff,
    )


def assert_partition_invariant(
    team: str,
    games: Iterable[GameResult],
    ranges: Sequence[tuple[date, date]],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
) -> PartitionResult:
    """Raise ``AggregationInvariantError`` when partition sums diverge."""
    result = partition_team_stats(team, games, ranges, policy=policy)
    if not result.ok:
        raise AggregationInvariantError(
            f"Partition invariant failed for {team!r}: "
            f"record {result.combined_record} != {result.full.record}, "
            f"point_diff {result.combined_point_diff} != "
            f"{result.full.point_differential}"
        )
    return result


def single_game_records(game: GameResult) -> tuple[TeamRecord, TeamRecord]:
    """Return the home and away records contributed by one game."""
    return (
        aggregate_record(game.home, [game]),
        aggregate_record(game.away, [game]),
    )


def check_mirror_records(game: GameResult) -> bool:
    """True when home and away each have exactly one game and outcomes mirror."""
    home, away = single_game_records(game)
    if home.games_played != 1 or away.games_played != 1:
        return False
    if game.home_score == game.away_score:
        return home.ties == 1 and away.ties == 1
    return (home.wins == 1 and away.losses == 1) or (
        home.losses == 1 and away.wins == 1
    )


def assert_mirror_records(game: GameResult) -> None:
    if not check_mirror_records(game):
        home, away = single_game_records(game)
        raise AggregationInvariantError(
            f"Mirror record invariant failed for {game!r}: "
            f"home={home!r}, away={away!r}"
        )


def league_point_diff_sum(
    games: Iterable[GameResult],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
    start: date | None = None,
    end: date | None = None,
) -> int:
    """Sum point differentials across every team in the league table."""
    standings = aggregate_standings(
        games, policy=policy, start=start, end=end
    )
    return sum(stats.point_differential for stats in standings.values())


def check_league_point_diff_zero_sum(
    games: Iterable[GameResult],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
    start: date | None = None,
    end: date | None = None,
) -> bool:
    """True when every team's scoring surplus cancels across the league."""
    return (
        league_point_diff_sum(
            games, policy=policy, start=start, end=end
        )
        == 0
    )


def assert_league_point_diff_zero_sum(
    games: Iterable[GameResult],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
    start: date | None = None,
    end: date | None = None,
) -> int:
    total = league_point_diff_sum(
        games, policy=policy, start=start, end=end
    )
    if total != 0:
        raise AggregationInvariantError(
            f"League point-diff sum is {total}, expected 0"
        )
    return total


def point_diff_counts_aligned(stats: TeamStats) -> bool:
    """True when games counted in record match games counted in point diff."""
    return stats.games_in_record == stats.games_in_point_diff


def count_all_point_diff_bounds(stats: TeamStats) -> bool:
    """Under COUNT_ALL, point-diff games never exceed record games."""
    return stats.games_in_point_diff <= stats.games_in_record
