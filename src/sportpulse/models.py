from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class Team:
    name: str
    abbreviation: str = ""

    def __post_init__(self) -> None:
        if not self.abbreviation:
            object.__setattr__(self, "abbreviation", self.name[:3].upper())


@dataclass(frozen=True)
class GameResult:
    home: str
    away: str
    home_score: int
    away_score: int
    played_on: date | None = None

    @property
    def margin(self) -> int:
        return abs(self.home_score - self.away_score)

    def involves(self, team: str) -> bool:
        return self.home == team or self.away == team

    def outcome_for(self, team: str) -> Literal["win", "loss", "tie"]:
        if self.home_score == self.away_score:
            return "tie"
        winner = self.home if self.home_score > self.away_score else self.away
        return "win" if team == winner else "loss"


@dataclass
class EloRating:
    team: str
    rating: float
    games_played: int = 0
    history: list[tuple[date | None, float]] = field(default_factory=list)

    def record(self, played_on: date | None, new_rating: float) -> None:
        self.history.append((played_on, self.rating))
        self.rating = new_rating
        self.games_played += 1
