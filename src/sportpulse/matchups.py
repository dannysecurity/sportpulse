from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore, chronological_order
from sportpulse.elo import EloCalculator, expected_score
from sportpulse.models import EloRating

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


def resolve_slate_date(
    matchups: list[Matchup],
    on_date: date,
    *,
    advance_if_empty: bool = False,
) -> tuple[date, bool]:
    """Pick the slate date, optionally rolling forward when the day is empty."""
    if matchups_for_date(matchups, on_date):
        return on_date, False
    if not advance_if_empty:
        return on_date, False
    next_date = next_slate_date(matchups, on_date)
    if next_date is None:
        return on_date, False
    return next_date, True


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
    calc = EloCalculator(k_factor=k_factor)
    ratings: dict[str, EloRating] = {}
    for box in chronological_order(scores):
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
    adjusted_home = home_rating + home_advantage
    home_prob = expected_score(adjusted_home, away_rating)
    away_prob = 1.0 - home_prob
    elo_gap = adjusted_home - away_rating
    return {
        "home": matchup.home,
        "away": matchup.away,
        "scheduled_on": matchup.scheduled_on.isoformat(),
        "home_rating": round(home_rating, 1),
        "away_rating": round(away_rating, 1),
        "home_win_prob": round(home_prob, 3),
        "away_win_prob": round(away_prob, 3),
        "home_spread": rating_gap_to_spread(elo_gap),
        "home_moneyline": probability_to_american_odds(home_prob),
        "away_moneyline": probability_to_american_odds(away_prob),
    }


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
    team_filter = report.get("team_filter")
    if isinstance(team_filter, str):
        title = f"{title}  [{team_filter}]"

    lines = [title, ""]
    if not matchups:
        lines.append("No games scheduled for this slate.")
        return "\n".join(lines)
    header = f"{'MATCHUP':<24} {'SPREAD':>7} {'HOME%':>6} {'AWAY%':>6} {'ML(H)':>7} {'ML(A)':>7}"
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
        lines.append(
            f"{label:<24} {spread_text:>7} {home_pct:>6} {away_pct:>6} {home_ml:>7} {away_ml:>7}"
        )

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
    advance_if_empty: bool = False,
    team: str | None = None,
) -> dict[str, object]:
    """Filter a slate to one day and attach odds-lite projections."""
    requested_date = on_date
    slate_date, advanced = resolve_slate_date(
        matchups,
        on_date,
        advance_if_empty=advance_if_empty,
    )
    slate = matchups_for_date(matchups, slate_date)
    if team is not None:
        slate = matchups_involving_team(slate, team)
    ratings = ratings_from_history(history or [], k_factor=k_factor)
    report: dict[str, object] = {
        "date": slate_date.isoformat(),
        "requested_date": requested_date.isoformat(),
        "advanced_to_next_slate": advanced,
        "matchups": [
            project_matchup(matchup, ratings, home_advantage=home_advantage)
            for matchup in slate
        ],
    }
    if team is not None:
        report["team_filter"] = team
    return report
