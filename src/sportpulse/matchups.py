from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.elo import EloCalculator, expected_score
from sportpulse.models import EloRating


@dataclass(frozen=True)
class Matchup:
    """Scheduled game without a final score."""

    home: str
    away: str
    scheduled_on: date


def load_matchups(path: Path | str) -> list[Matchup]:
    """Load scheduled matchups from a JSON file."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"matchups file not found: {file_path}")

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "games" in payload:
        records = payload["games"]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("matchups JSON must be a list or an object with a games array")

    if not isinstance(records, list):
        raise ValueError("games must be a list when present")

    matchups: list[Matchup] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"matchup at index {index} must be an object")

        home = record.get("home")
        away = record.get("away")
        scheduled_on = record.get("scheduled_on")
        if not isinstance(home, str) or not isinstance(away, str) or not home or not away:
            raise ValueError(f"matchup at index {index}: home and away are required strings")
        if not isinstance(scheduled_on, str):
            raise ValueError(f"matchup at index {index}: scheduled_on must be an ISO date string")

        try:
            on_date = date.fromisoformat(scheduled_on)
        except ValueError as exc:
            raise ValueError(f"matchup at index {index}: invalid scheduled_on: {scheduled_on!r}") from exc

        matchups.append(Matchup(home=home, away=away, scheduled_on=on_date))
    return matchups


def matchups_for_date(matchups: list[Matchup], on_date: date) -> list[Matchup]:
    """Return matchups scheduled on a specific calendar day."""
    return [matchup for matchup in matchups if matchup.scheduled_on == on_date]


def ratings_from_history(
    scores: list[BoxScore],
    *,
    k_factor: float = 20.0,
) -> dict[str, float]:
    """Replay historical results and return each team's current ELO rating."""
    calc = EloCalculator(k_factor=k_factor)
    ratings: dict[str, EloRating] = {}
    for box in scores:
        calc.apply_result(
            ratings,
            box.home,
            box.away,
            box.home_score,
            box.away_score,
            box.played_on,
        )
    return {team: rating.rating for team, rating in ratings.items()}


def project_matchup(
    matchup: Matchup,
    ratings: dict[str, float],
    *,
    home_advantage: float = 65.0,
) -> dict[str, object]:
    """Odds-lite win probabilities from ELO ratings and home-court adjustment."""
    home_rating = ratings.get(matchup.home, 1500.0)
    away_rating = ratings.get(matchup.away, 1500.0)
    home_prob = expected_score(home_rating + home_advantage, away_rating)
    away_prob = 1.0 - home_prob
    return {
        "home": matchup.home,
        "away": matchup.away,
        "scheduled_on": matchup.scheduled_on.isoformat(),
        "home_rating": round(home_rating, 1),
        "away_rating": round(away_rating, 1),
        "home_win_prob": round(home_prob, 3),
        "away_win_prob": round(away_prob, 3),
    }


def build_matchups_report(
    matchups: list[Matchup],
    *,
    on_date: date,
    history: list[BoxScore] | None = None,
    k_factor: float = 20.0,
    home_advantage: float = 65.0,
) -> dict[str, object]:
    """Filter a slate to one day and attach odds-lite projections."""
    slate = matchups_for_date(matchups, on_date)
    ratings = ratings_from_history(history or [], k_factor=k_factor)
    return {
        "date": on_date.isoformat(),
        "matchups": [
            project_matchup(matchup, ratings, home_advantage=home_advantage)
            for matchup in slate
        ],
    }
