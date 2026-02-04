from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Literal

from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, TeamStats, aggregate_team_stats
from sportpulse.stats import TeamRecord, aggregate_record, games_in_range


@dataclass(frozen=True)
class TeamStanding:
    """League-table row for one team."""

    team: str
    stats: TeamStats

    @property
    def record(self) -> TeamRecord:
        return self.stats.record

    @property
    def win_pct(self) -> float:
        return self.stats.record.win_pct

    @property
    def point_differential(self) -> int:
        return self.stats.point_differential


@dataclass(frozen=True)
class VenueSplit:
    """Win/loss record split by home and away appearances."""

    home: TeamRecord
    away: TeamRecord

    @property
    def combined(self) -> TeamRecord:
        return self.home + self.away


def discover_teams(games: Iterable[GameResult]) -> frozenset[str]:
    """Collect every team name that appears as home or away."""
    names: set[str] = set()
    for game in games:
        names.add(game.home)
        names.add(game.away)
    return frozenset(names)


def aggregate_standings(
    games: Iterable[GameResult],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, TeamStats]:
    """Roll up stats for every team discovered in ``games``."""
    game_list = list(games)
    if start is not None and end is not None:
        scoped_games = games_in_range(game_list, start, end)
    else:
        scoped_games = game_list
    teams = discover_teams(scoped_games)
    return {
        team: aggregate_team_stats(
            team,
            game_list,
            policy=policy,
            start=start,
            end=end,
        )
        for team in teams
    }


def rank_standings(
    standings: dict[str, TeamStats],
    *,
    tie_breaker: Literal["win_pct", "point_diff", "team_name"] = "win_pct",
) -> list[TeamStanding]:
    """Sort teams for a league table with deterministic tie-breaking."""
    rows = [TeamStanding(team=team, stats=stats) for team, stats in standings.items()]

    def sort_key(row: TeamStanding) -> tuple:
        primary = -row.win_pct if tie_breaker == "win_pct" else -row.point_differential
        secondary = -row.point_differential
        tertiary = row.team
        if tie_breaker == "point_diff":
            return (-row.point_differential, -row.win_pct, tertiary)
        if tie_breaker == "team_name":
            return (tertiary,)
        return (primary, secondary, tertiary)

    return sorted(rows, key=sort_key)


def head_to_head_record(
    team: str,
    opponent: str,
    games: Iterable[GameResult],
) -> TeamRecord:
    """Record for ``team`` in games where ``opponent`` is the other participant."""
    matchups = [
        game
        for game in games
        if game.involves(team) and game.involves(opponent) and team != opponent
    ]
    return aggregate_record(team, matchups)


def venue_split(team: str, games: Iterable[GameResult]) -> VenueSplit:
    """Split a team's record by home and away appearances."""
    home_games = [game for game in games if game.home == team]
    away_games = [game for game in games if game.away == team]
    return VenueSplit(
        home=aggregate_record(team, home_games),
        away=aggregate_record(team, away_games),
    )


def standings_in_range(
    games: Iterable[GameResult],
    start: date,
    end: date,
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
) -> dict[str, TeamStats]:
    """Convenience wrapper for date-filtered league standings."""
    return aggregate_standings(games, policy=policy, start=start, end=end)


def games_for_teams(
    games: Iterable[GameResult],
    teams: Iterable[str],
) -> list[GameResult]:
    """Return games where at least one listed team participates."""
    team_set = frozenset(teams)
    return [
        game
        for game in games
        if game.home in team_set or game.away in team_set
    ]
