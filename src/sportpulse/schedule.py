from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sportpulse.models import GameResult
from sportpulse.stats import aggregate_record, aggregate_record_in_range, games_in_range


@dataclass
class Schedule:
    """Team schedule with date-range filtering."""

    team: str
    games: list[GameResult] = field(default_factory=list)

    def add(self, game: GameResult) -> None:
        if game.home != self.team and game.away != self.team:
            raise ValueError(f"{self.team} is not a participant in {game}")
        self.games.append(game)

    def between(self, start: date, end: date) -> list[GameResult]:
        return games_in_range(self.games, start, end)

    def record(self) -> dict[str, int]:
        return aggregate_record(self.team, self.games).to_dict()

    def record_in_range(self, start: date, end: date) -> dict[str, int]:
        return aggregate_record_in_range(self.team, self.games, start, end).to_dict()

    def to_json(self) -> dict[str, object]:
        return {
            "team": self.team,
            "games": [
                {
                    "home": g.home,
                    "away": g.away,
                    "home_score": g.home_score,
                    "away_score": g.away_score,
                    "played_on": g.played_on.isoformat() if g.played_on else None,
                }
                for g in self.games
            ],
            "record": self.record(),
        }
