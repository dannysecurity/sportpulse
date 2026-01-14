from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sportpulse.models import GameResult


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
        return [
            g
            for g in self.games
            if g.played_on is not None and start <= g.played_on <= end
        ]

    def record(self) -> dict[str, int]:
        wins = losses = ties = 0
        for game in self.games:
            outcome = game.outcome_for(self.team)
            if outcome == "win":
                wins += 1
            elif outcome == "loss":
                losses += 1
            else:
                ties += 1
        return {"wins": wins, "losses": losses, "ties": ties}

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
