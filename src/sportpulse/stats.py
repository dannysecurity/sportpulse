from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sportpulse.models import GameResult


@dataclass(frozen=True)
class TeamRecord:
    """Win/loss/tie rollup for a team across one or more games."""

    wins: int = 0
    losses: int = 0
    ties: int = 0

    @property
    def games_played(self) -> int:
        return self.wins + self.losses + self.ties

    @property
    def win_pct(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played

    def to_dict(self) -> dict[str, int]:
        return {"wins": self.wins, "losses": self.losses, "ties": self.ties}

    def __add__(self, other: TeamRecord) -> TeamRecord:
        return TeamRecord(
            wins=self.wins + other.wins,
            losses=self.losses + other.losses,
            ties=self.ties + other.ties,
        )


def games_in_range(
    games: Iterable[GameResult],
    start: date,
    end: date,
) -> list[GameResult]:
    """Return dated games whose ``played_on`` falls within ``[start, end]``."""
    return [
        game
        for game in games
        if game.played_on is not None and start <= game.played_on <= end
    ]


def aggregate_record(team: str, games: Iterable[GameResult]) -> TeamRecord:
    """Roll up outcomes for ``team`` across all supplied games."""
    wins = losses = ties = 0
    for game in games:
        outcome = game.outcome_for(team)
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        else:
            ties += 1
    return TeamRecord(wins=wins, losses=losses, ties=ties)


def aggregate_record_in_range(
    team: str,
    games: Iterable[GameResult],
    start: date,
    end: date,
) -> TeamRecord:
    """Roll up outcomes for dated games inside the inclusive window."""
    return aggregate_record(team, games_in_range(games, start, end))


def point_differential(team: str, games: Iterable[GameResult]) -> int:
    """Net points scored minus points allowed for ``team``."""
    total = 0
    for game in games:
        if game.home == team:
            total += game.home_score - game.away_score
        elif game.away == team:
            total += game.away_score - game.home_score
    return total
