from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.elo import expected_score
from sportpulse.ratings import replay_elo_ratings
from sportpulse.projections import (
    TeamScoringProfile,
    build_scoring_profiles,
    project_game_total,
)

_matchups_cache: dict[str, tuple[int, int, list[Matchup]]] = {}


@dataclass(frozen=True)
class Matchup:
    """Scheduled game without a final score."""

    home: str
    away: str
    scheduled_on: date


def clear_matchups_cache() -> None:
    """Clear the in-process matchups file cache."""
    _matchups_cache.clear()


def _parse_matchups_payload(payload: object) -> list[Matchup]:
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


def load_matchups(path: Path | str) -> list[Matchup]:
    """Load scheduled matchups from a JSON file.

    Parsed results are cached in-process keyed by resolved path and file
    modification time so repeated loads skip disk I/O and parsing.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"matchups file not found: {file_path}")

    resolved_path = file_path.resolve()
    stat = resolved_path.stat()
    cache_key = str(resolved_path)
    cached = _matchups_cache.get(cache_key)
    if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]

    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    matchups = _parse_matchups_payload(payload)
    _matchups_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, matchups)
    return matchups


def matchups_for_date(matchups: list[Matchup], on_date: date) -> list[Matchup]:
    """Return matchups scheduled on a specific calendar day."""
    return [matchup for matchup in matchups if matchup.scheduled_on == on_date]


def next_slate_date(matchups: list[Matchup], on_or_after: date) -> date | None:
    """Return the earliest scheduled date on or after ``on_or_after``."""
    future_dates = sorted(
        {matchup.scheduled_on for matchup in matchups if matchup.scheduled_on >= on_or_after}
    )
    return future_dates[0] if future_dates else None


def last_slate_date(matchups: list[Matchup]) -> date | None:
    """Return the latest scheduled date in the slate file."""
    if not matchups:
        return None
    return max(matchup.scheduled_on for matchup in matchups)


def resolve_slate_date(
    matchups: list[Matchup],
    on_date: date,
    *,
    advance_if_empty: bool = False,
) -> tuple[date, bool, bool]:
    """Pick the slate date, optionally rolling forward or back when the day is empty.

    Returns ``(slate_date, advanced_to_next_slate, advanced_to_last_slate)``.
    When ``advance_if_empty`` is set and the requested day has no games, the
    next future slate is preferred; if every game is in the past, the most
    recent slate is shown instead.
    """
    if matchups_for_date(matchups, on_date):
        return on_date, False, False
    if not advance_if_empty:
        return on_date, False, False
    next_date = next_slate_date(matchups, on_date)
    if next_date is not None:
        return next_date, True, False
    last_date = last_slate_date(matchups)
    if last_date is not None:
        return last_date, False, True
    return on_date, False, False


def matchups_involving_team(
    matchups: list[Matchup],
    team: str,
    *,
    on_date: date | None = None,
) -> list[Matchup]:
    """Return matchups that include ``team``, optionally limited to one day."""
    filtered = [
        matchup
        for matchup in matchups
        if matchup.home == team or matchup.away == team
    ]
    if on_date is None:
        return filtered
    return [matchup for matchup in filtered if matchup.scheduled_on == on_date]


def probability_to_american_odds(prob: float) -> int:
    """Convert a win probability (0, 1) to American moneyline odds."""
    if not 0.0 < prob < 1.0:
        raise ValueError("probability must be between 0 and 1 exclusive")
    if prob >= 0.5:
        return round(-100 * prob / (1 - prob))
    return round(100 * (1 - prob) / prob)


def rating_gap_to_spread(elo_gap: float, *, points_per_100_elo: float = 4.0) -> float:
    """Estimate the home point spread from an ELO gap (home minus away).

    A negative spread means the home team is favored (e.g. -4.5).
    """
    return round(-elo_gap / 100 * points_per_100_elo, 1)


def ratings_from_history(
    scores: list[BoxScore],
    *,
    k_factor: float = 20.0,
) -> dict[str, float]:
    """Replay historical results and return each team's current ELO rating."""
    replay = replay_elo_ratings(scores, k_factor=k_factor)
    return {team: rating.rating for team, rating in replay.ratings.items()}


def project_matchup(
    matchup: Matchup,
    ratings: dict[str, float],
    *,
    home_advantage: float = 65.0,
    points_per_100_elo: float = 4.0,
    home_court_points: float = 2.5,
    scoring_profiles: dict[str, TeamScoringProfile] | None = None,
) -> dict[str, object]:
    """Odds-lite win probabilities from ELO ratings and home-court adjustment."""
    home_rating = ratings.get(matchup.home, 1500.0)
    away_rating = ratings.get(matchup.away, 1500.0)
    adjusted_home = home_rating + home_advantage
    home_prob = expected_score(adjusted_home, away_rating)
    away_prob = 1.0 - home_prob
    elo_gap = adjusted_home - away_rating
    projection: dict[str, object] = {
        "home": matchup.home,
        "away": matchup.away,
        "scheduled_on": matchup.scheduled_on.isoformat(),
        "home_rating": round(home_rating, 1),
        "away_rating": round(away_rating, 1),
        "home_win_prob": round(home_prob, 3),
        "away_win_prob": round(away_prob, 3),
        "home_spread": rating_gap_to_spread(elo_gap, points_per_100_elo=points_per_100_elo),
        "home_moneyline": probability_to_american_odds(home_prob),
        "away_moneyline": probability_to_american_odds(away_prob),
    }
    if scoring_profiles is not None:
        projection.update(
            project_game_total(
                matchup.home,
                matchup.away,
                scoring_profiles,
                home_court_points=home_court_points,
            )
        )
    return projection


def build_slate_summary(matchups: list[dict[str, object]]) -> dict[str, object]:
    """Summarize odds-lite projections across a day's slate."""
    if not matchups:
        return {
            "games": 0,
            "home_favorites": 0,
            "away_favorites": 0,
            "pick_em_games": 0,
            "avg_projected_total": None,
            "highest_total_game": None,
            "biggest_spread_game": None,
            "closest_game": None,
            "has_scoring_projections": False,
        }

    home_favorites = 0
    away_favorites = 0
    pick_em_games = 0
    totals: list[float] = []
    highest_total_game: dict[str, object] | None = None
    biggest_spread_game: dict[str, object] | None = None
    closest_game: dict[str, object] | None = None
    biggest_spread_magnitude = -1.0
    closest_spread = float("inf")

    for game in matchups:
        spread = game.get("home_spread")
        if not isinstance(spread, (int, float)):
            continue

        if spread < 0:
            home_favorites += 1
        elif spread > 0:
            away_favorites += 1
        else:
            pick_em_games += 1

        spread_magnitude = abs(float(spread))
        if spread_magnitude > biggest_spread_magnitude:
            biggest_spread_magnitude = spread_magnitude
            biggest_spread_game = game
        if spread_magnitude < closest_spread:
            closest_spread = spread_magnitude
            closest_game = game

        total = game.get("projected_total")
        if isinstance(total, (int, float)):
            totals.append(float(total))
            if highest_total_game is None or float(total) > float(
                highest_total_game.get("projected_total", 0)
            ):
                highest_total_game = game

    avg_total = round(sum(totals) / len(totals), 1) if totals else None

    def _matchup_label(game: dict[str, object] | None) -> str | None:
        if game is None:
            return None
        home = game.get("home")
        away = game.get("away")
        if isinstance(home, str) and isinstance(away, str):
            return f"{away} @ {home}"
        return None

    return {
        "games": len(matchups),
        "home_favorites": home_favorites,
        "away_favorites": away_favorites,
        "pick_em_games": pick_em_games,
        "avg_projected_total": avg_total,
        "highest_total_game": _matchup_label(highest_total_game),
        "biggest_spread_game": _matchup_label(biggest_spread_game),
        "closest_game": _matchup_label(closest_game),
        "has_scoring_projections": bool(totals),
    }


def _format_slate_summary(summary: dict[str, object]) -> str:
    """Render a one-line odds-lite slate digest for terminal output."""
    games = summary.get("games", 0)
    if not isinstance(games, int) or games == 0:
        return ""

    parts = [
        f"{summary['home_favorites']} home fav",
        f"{summary['away_favorites']} away fav",
    ]
    if summary.get("pick_em_games"):
        parts.append(f"{summary['pick_em_games']} pick'em")

    if summary.get("has_scoring_projections") and summary.get("avg_projected_total") is not None:
        parts.append(f"avg O/U {summary['avg_projected_total']}")

    if summary.get("biggest_spread_game"):
        parts.append(f"biggest spread: {summary['biggest_spread_game']}")
    if summary.get("closest_game"):
        parts.append(f"closest: {summary['closest_game']}")

    return "Slate: " + ", ".join(parts)


def format_matchups_table(report: dict[str, object]) -> str:
    """Render a matchups report as a fixed-width terminal table."""
    matchups = report.get("matchups", [])
    if not isinstance(matchups, list):
        raise ValueError("report matchups must be a list")

    title = f"{report['date']} — {len(matchups)} game(s)"
    if report.get("advanced_to_next_slate"):
        requested = report.get("requested_date")
        if isinstance(requested, str):
            title = f"{title}  (requested {requested}, next slate)"
    elif report.get("advanced_to_last_slate"):
        requested = report.get("requested_date")
        if isinstance(requested, str):
            title = f"{title}  (requested {requested}, last slate)"
    team_filter = report.get("team_filter")
    if isinstance(team_filter, str):
        title = f"{title}  [{team_filter}]"

    lines = [title, ""]
    if not matchups:
        lines.append("No games scheduled for this slate.")
        return "\n".join(lines)
    show_totals = any(
        isinstance(game, dict) and "projected_total" in game for game in matchups
    )
    if show_totals:
        header = (
            f"{'MATCHUP':<24} {'SPREAD':>7} {'HOME%':>6} {'AWAY%':>6} "
            f"{'ML(H)':>7} {'ML(A)':>7} {'PROJ':>5} {'O/U':>6}"
        )
    else:
        header = (
            f"{'MATCHUP':<24} {'SPREAD':>7} {'HOME%':>6} {'AWAY%':>6} "
            f"{'ML(H)':>7} {'ML(A)':>7}"
        )
    lines.extend([header, "-" * len(header)])

    for game in matchups:
        if not isinstance(game, dict):
            continue
        label = f"{game['away']} @ {game['home']}"
        spread = game["home_spread"]
        spread_text = f"{spread:+.1f}" if isinstance(spread, (int, float)) else str(spread)
        home_pct = f"{float(game['home_win_prob']) * 100:.0f}%"
        away_pct = f"{float(game['away_win_prob']) * 100:.0f}%"
        home_ml = _format_moneyline(game["home_moneyline"])
        away_ml = _format_moneyline(game["away_moneyline"])
        row = (
            f"{label:<24} {spread_text:>7} {home_pct:>6} {away_pct:>6} "
            f"{home_ml:>7} {away_ml:>7}"
        )
        if show_totals:
            home_proj = game.get("home_projected_points", "-")
            away_proj = game.get("away_projected_points", "-")
            total = game.get("projected_total", "-")
            proj_text = (
                f"{home_proj:.0f}-{away_proj:.0f}"
                if isinstance(home_proj, (int, float)) and isinstance(away_proj, (int, float))
                else "-"
            )
            total_text = f"{total:.1f}" if isinstance(total, (int, float)) else str(total)
            row = f"{row} {proj_text:>5} {total_text:>6}"
        lines.append(row)

    summary = report.get("summary")
    if isinstance(summary, dict) and summary.get("games"):
        lines.extend(["", _format_slate_summary(summary)])

    return "\n".join(lines)


def _format_moneyline(value: object) -> str:
    if not isinstance(value, int):
        return str(value)
    return f"+{value}" if value > 0 else str(value)


def build_matchups_report(
    matchups: list[Matchup],
    *,
    on_date: date,
    history: list[BoxScore] | None = None,
    k_factor: float = 20.0,
    home_advantage: float = 65.0,
    points_per_100_elo: float = 4.0,
    home_court_points: float = 2.5,
    advance_if_empty: bool = False,
    team: str | None = None,
) -> dict[str, object]:
    """Filter a slate to one day and attach odds-lite projections."""
    requested_date = on_date
    slate_date, advanced_next, advanced_last = resolve_slate_date(
        matchups,
        on_date,
        advance_if_empty=advance_if_empty,
    )
    slate = matchups_for_date(matchups, slate_date)
    if team is not None:
        slate = matchups_involving_team(slate, team)
    ratings = ratings_from_history(history or [], k_factor=k_factor)
    scoring_profiles = build_scoring_profiles(history) if history else None
    projected = [
        project_matchup(
            matchup,
            ratings,
            home_advantage=home_advantage,
            points_per_100_elo=points_per_100_elo,
            home_court_points=home_court_points,
            scoring_profiles=scoring_profiles,
        )
        for matchup in slate
    ]
    report: dict[str, object] = {
        "date": slate_date.isoformat(),
        "requested_date": requested_date.isoformat(),
        "advanced_to_next_slate": advanced_next,
        "advanced_to_last_slate": advanced_last,
        "matchups": projected,
        "summary": build_slate_summary(projected),
    }
    if team is not None:
        report["team_filter"] = team
    return report
