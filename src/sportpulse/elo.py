from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from sportpulse.models import EloRating


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that team A beats team B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


@dataclass
class EloCalculator:
    """Standard ELO update with margin-of-victory scaling."""

    k_factor: float = 20.0
    home_advantage: float = 0.0
    max_margin_multiplier: float | None = None

    def actual_score(self, score_a: int, score_b: int) -> tuple[float, float]:
        if score_a > score_b:
            return 1.0, 0.0
        if score_b > score_a:
            return 0.0, 1.0
        return 0.5, 0.5

    def margin_multiplier(self, score_a: int, score_b: int) -> float:
        """Scale K by log2(margin + 1); one-possession games keep the base K.

        When ``max_margin_multiplier`` is set, blowout scaling is capped so a
        single lopsided result cannot move team power ratings too far.
        """
        margin = abs(score_a - score_b)
        if margin <= 1:
            return 1.0
        multiplier = math.log(margin + 1) / math.log(2)
        if self.max_margin_multiplier is not None:
            return min(multiplier, self.max_margin_multiplier)
        return multiplier

    def update(
        self,
        rating_a: float,
        rating_b: float,
        *,
        score_a: int,
        score_b: int,
        team_a_home: bool = True,
    ) -> tuple[float, float]:
        adj_a = rating_a + (self.home_advantage if team_a_home else 0.0)
        adj_b = rating_b + (0.0 if team_a_home else self.home_advantage)

        expected_a = expected_score(adj_a, adj_b)
        expected_b = 1.0 - expected_a
        actual_a, actual_b = self.actual_score(score_a, score_b)
        multiplier = self.margin_multiplier(score_a, score_b)
        delta = self.k_factor * multiplier

        new_a = rating_a + delta * (actual_a - expected_a)
        new_b = rating_b + delta * (actual_b - expected_b)
        return round(new_a, 1), round(new_b, 1)

    def apply_result(
        self,
        ratings: dict[str, EloRating],
        home: str,
        away: str,
        home_score: int,
        away_score: int,
        played_on: date | None = None,
    ) -> tuple[float, float]:
        home_rating = ratings.setdefault(home, EloRating(team=home, rating=1500.0))
        away_rating = ratings.setdefault(away, EloRating(team=away, rating=1500.0))

        new_home, new_away = self.update(
            home_rating.rating,
            away_rating.rating,
            score_a=home_score,
            score_b=away_score,
            team_a_home=True,
        )
        home_rating.record(played_on, new_home)
        away_rating.record(played_on, new_away)
        return new_home, new_away

    def trend(self, rating: EloRating) -> list[dict[str, object]]:
        points = rating.history + [(None, rating.rating)]
        return [
            {
                "played_on": played_on.isoformat() if played_on else None,
                "rating": value,
            }
            for played_on, value in points
        ]
