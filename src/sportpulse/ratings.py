from __future__ import annotations

from dataclasses import dataclass

from sportpulse.boxscore import BoxScore, chronological_order
from sportpulse.elo import EloCalculator
from sportpulse.models import EloRating

DEFAULT_STARTING_RATING = 1500.0


@dataclass(frozen=True)
class EloReplay:
    """Result of replaying box scores through the ELO calculator."""

    calculator: EloCalculator
    ratings: dict[str, EloRating]
    games_replayed: int


def replay_elo_ratings(
    scores: list[BoxScore],
    *,
    k_factor: float = 20.0,
    home_advantage: float = 0.0,
) -> EloReplay:
    """Replay historical results and return each team's ELO state."""
    calc = EloCalculator(k_factor=k_factor, home_advantage=home_advantage)
    ratings: dict[str, EloRating] = {}
    ordered = chronological_order(scores)
    for box in ordered:
        calc.apply_result(
            ratings,
            box.home,
            box.away,
            box.home_score,
            box.away_score,
            box.played_on,
        )
    return EloReplay(calculator=calc, ratings=ratings, games_replayed=len(ordered))


def rank_elo_ratings(ratings: dict[str, EloRating]) -> list[dict[str, object]]:
    """Sort teams by current ELO (desc), breaking ties alphabetically."""
    rows: list[dict[str, object]] = []
    sorted_teams = sorted(
        ratings.values(),
        key=lambda entry: (-entry.rating, entry.team),
    )
    for rank, entry in enumerate(sorted_teams, start=1):
        rows.append(
            {
                "rank": rank,
                "team": entry.team,
                "rating": entry.rating,
                "games_played": entry.games_played,
                "delta": round(entry.rating - DEFAULT_STARTING_RATING, 1),
            }
        )
    return rows


def build_ratings_leaderboard(
    scores: list[BoxScore],
    *,
    k_factor: float = 20.0,
    home_advantage: float = 0.0,
) -> dict[str, object]:
    """Replay a season file and return a ranked ELO leaderboard."""
    replay = replay_elo_ratings(
        scores,
        k_factor=k_factor,
        home_advantage=home_advantage,
    )
    return {
        "k_factor": k_factor,
        "home_advantage": home_advantage,
        "games_replayed": replay.games_replayed,
        "ratings": rank_elo_ratings(replay.ratings),
    }


def format_ratings_table(report: dict[str, object]) -> str:
    """Render a ratings leaderboard as a fixed-width terminal table."""
    ratings = report.get("ratings", [])
    if not isinstance(ratings, list):
        raise ValueError("report ratings must be a list")

    games = report.get("games_replayed", 0)
    title = f"ELO leaderboard — {games} game(s) replayed"
    lines = [title, ""]
    if not ratings:
        lines.append("No games to replay.")
        return "\n".join(lines)

    header = f"{'RK':>3} {'TEAM':<16} {'ELO':>7} {'GP':>4} {'Δ':>7}"
    lines.extend([header, "-" * len(header)])
    for row in ratings:
        if not isinstance(row, dict):
            continue
        delta = row["delta"]
        delta_text = f"{delta:+.1f}" if isinstance(delta, (int, float)) else str(delta)
        lines.append(
            f"{row['rank']:>3} {row['team']:<16} {row['rating']:>7.1f} "
            f"{row['games_played']:>4} {delta_text:>7}"
        )
    return "\n".join(lines)
