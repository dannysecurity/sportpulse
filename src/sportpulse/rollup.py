from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Iterable

from sportpulse.models import GameResult
from sportpulse.stats import (
    TeamRecord,
    aggregate_record,
    games_in_range,
    point_differential,
)


class ParticipationPolicy(str, Enum):
    """How non-participant games are treated when rolling up team stats."""

    COUNT_ALL = "count_all"
    """Count every supplied game (legacy ``aggregate_record`` behavior)."""

    PARTICIPANT_ONLY = "participant_only"
    """Ignore games where ``team`` is not home or away."""


def filter_participant_games(
    team: str, games: Iterable[GameResult]
) -> list[GameResult]:
    """Return only games where ``team`` is home or away."""
    return [game for game in games if game.involves(team)]


def _select_games(
    team: str,
    games: Iterable[GameResult],
    *,
    policy: ParticipationPolicy,
    start: date | None = None,
    end: date | None = None,
) -> list[GameResult]:
    selected = list(games)
    if start is not None and end is not None:
        selected = games_in_range(selected, start, end)
    if policy == ParticipationPolicy.PARTICIPANT_ONLY:
        selected = filter_participant_games(team, selected)
    return selected


@dataclass(frozen=True)
class TeamStats:
    """Unified win/loss record and scoring rollup for a team."""

    record: TeamRecord
    point_differential: int
    games_in_record: int
    games_in_point_diff: int

    @property
    def avg_margin(self) -> float:
        if self.games_in_point_diff == 0:
            return 0.0
        return self.point_differential / self.games_in_point_diff

    def to_dict(self) -> dict[str, object]:
        return {
            "record": self.record.to_dict(),
            "point_differential": self.point_differential,
            "avg_margin": self.avg_margin,
        }


def aggregate_team_stats(
    team: str,
    games: Iterable[GameResult],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.COUNT_ALL,
    start: date | None = None,
    end: date | None = None,
) -> TeamStats:
    """Roll up record and point differential under an explicit participation policy."""
    selected = _select_games(team, games, policy=policy, start=start, end=end)
    record = aggregate_record(team, selected)
    pd = point_differential(team, selected)
    pd_games = sum(1 for game in selected if game.involves(team))
    return TeamStats(
        record=record,
        point_differential=pd,
        games_in_record=record.games_played,
        games_in_point_diff=pd_games,
    )
