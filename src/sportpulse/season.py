from __future__ import annotations

from datetime import date

from sportpulse.boxscore import BoxScore
from sportpulse.elo import EloCalculator
from sportpulse.models import EloRating
from sportpulse.schedule import Schedule


def build_season_report(
    team: str,
    scores: list[BoxScore],
    *,
    start: date | None = None,
    end: date | None = None,
    k_factor: float = 20.0,
) -> dict[str, object]:
    """Summarize a team's record and ELO trend from parsed box scores."""
    schedule = Schedule(team=team)
    for box in scores:
        if box.home == team or box.away == team:
            schedule.add(box.to_result())

    report: dict[str, object] = {
        "team": team,
        "games_played": len(schedule.games),
        "record": schedule.record(),
        "point_differential": schedule.point_diff(),
    }
    if start is not None and end is not None:
        report["record_in_range"] = schedule.record_in_range(start, end)
        report["point_differential_in_range"] = schedule.point_diff_in_range(start, end)
        report["stats_in_range"] = schedule.team_stats(start=start, end=end).to_dict()

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

    if team not in ratings:
        report["elo_rating"] = 1500.0
        report["elo_trend"] = [{"played_on": None, "rating": 1500.0}]
    else:
        report["elo_rating"] = ratings[team].rating
        report["elo_trend"] = calc.trend(ratings[team])

    return report
