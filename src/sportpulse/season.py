from __future__ import annotations

from datetime import date

from sportpulse.boxscore import BoxScore
from sportpulse.ratings import replay_elo_ratings
from sportpulse.schedule import Schedule, schedule_from_scores


def build_season_report(
    team: str,
    scores: list[BoxScore],
    *,
    start: date | None = None,
    end: date | None = None,
    k_factor: float = 20.0,
) -> dict[str, object]:
    """Summarize a team's record and ELO trend from parsed box scores."""
    schedule = schedule_from_scores(team, scores)

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

    replay = replay_elo_ratings(scores, k_factor=k_factor)

    if team not in replay.ratings:
        report["elo_rating"] = 1500.0
        report["elo_trend"] = [{"played_on": None, "rating": 1500.0}]
    else:
        team_rating = replay.ratings[team]
        report["elo_rating"] = team_rating.rating
        report["elo_trend"] = replay.calculator.trend(team_rating)

    return report
