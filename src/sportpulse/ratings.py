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


def _team_update_entry(before: float, after: float) -> dict[str, object]:
    return {
        "before": before,
        "after": after,
        "delta": round(after - before, 1),
    }


def apply_game_to_ratings(
    ratings: dict[str, EloRating],
    game: BoxScore,
    *,
    calculator: EloCalculator,
) -> dict[str, dict[str, object]]:
    """Apply one result to in-memory ratings and return per-team update details."""
    home_before = ratings.get(
        game.home, EloRating(team=game.home, rating=DEFAULT_STARTING_RATING)
    ).rating
    away_before = ratings.get(
        game.away, EloRating(team=game.away, rating=DEFAULT_STARTING_RATING)
    ).rating

    new_home, new_away = calculator.apply_result(
        ratings,
        game.home,
        game.away,
        game.home_score,
        game.away_score,
        game.played_on,
    )
    return {
        game.home: _team_update_entry(home_before, new_home),
        game.away: _team_update_entry(away_before, new_away),
    }


def build_rating_update_report(
    game: BoxScore,
    *,
    history: list[BoxScore] | None = None,
    k_factor: float = 20.0,
    home_advantage: float = 0.0,
    include_leaderboard: bool = False,
) -> dict[str, object]:
    """Bootstrap ratings from history, apply a new result, and return an update report."""
    replay = replay_elo_ratings(
        history or [],
        k_factor=k_factor,
        home_advantage=home_advantage,
    )
    updates = apply_game_to_ratings(replay.ratings, game, calculator=replay.calculator)
    report: dict[str, object] = {
        "game": game.summary(),
        "k_factor": k_factor,
        "home_advantage": home_advantage,
        "games_replayed": replay.games_replayed,
        "updates": updates,
    }
    if include_leaderboard:
        report["ratings"] = rank_elo_ratings(replay.ratings)
    return report


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
