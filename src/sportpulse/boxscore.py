from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sportpulse.models import GameResult


def chronological_order(scores: list[BoxScore]) -> list[BoxScore]:
    """Sort box scores by ``played_on`` for stable ELO replay.

    Undated games are replayed after all dated games; ties preserve input order.
    """
    return sorted(scores, key=lambda box: (box.played_on is None, box.played_on))


@dataclass(frozen=True)
class BoxScore:
    """Single-game box score with basic summary helpers."""

    home: str
    away: str
    home_score: int
    away_score: int
    played_on: date | None = None

    def winner(self) -> str | None:
        if self.home_score > self.away_score:
            return self.home
        if self.away_score > self.home_score:
            return self.away
        return None

    def is_overtime_needed(self, regulation_minutes: int = 48) -> bool:
        """Placeholder hook for future period-aware parsing."""
        return self.home_score == self.away_score

    def to_result(self) -> GameResult:
        return GameResult(
            home=self.home,
            away=self.away,
            home_score=self.home_score,
            away_score=self.away_score,
            played_on=self.played_on,
        )

    def summary(self) -> dict[str, object]:
        winner = self.winner()
        return {
            "home": self.home,
            "away": self.away,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "margin": abs(self.home_score - self.away_score),
            "winner": winner,
            "played_on": self.played_on.isoformat() if self.played_on else None,
        }
