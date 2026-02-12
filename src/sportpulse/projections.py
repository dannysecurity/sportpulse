from __future__ import annotations

from dataclasses import dataclass

from sportpulse.boxscore import BoxScore


@dataclass(frozen=True)
class TeamScoringProfile:
    """Average points scored and allowed from historical box scores."""

    team: str
    games: int
    avg_points_for: float
    avg_points_against: float


def build_scoring_profiles(scores: list[BoxScore]) -> dict[str, TeamScoringProfile]:
    """Compute per-team scoring pace from played games."""
    points_for: dict[str, list[int]] = {}
    points_against: dict[str, list[int]] = {}

    for box in scores:
        for team, scored, allowed in (
            (box.home, box.home_score, box.away_score),
            (box.away, box.away_score, box.home_score),
        ):
            points_for.setdefault(team, []).append(scored)
            points_against.setdefault(team, []).append(allowed)

    profiles: dict[str, TeamScoringProfile] = {}
    for team in sorted(set(points_for) | set(points_against)):
        scored = points_for.get(team, [])
        allowed = points_against.get(team, [])
        games = max(len(scored), len(allowed))
        if games == 0:
            continue
        profiles[team] = TeamScoringProfile(
            team=team,
            games=games,
            avg_points_for=sum(scored) / len(scored) if scored else 0.0,
            avg_points_against=sum(allowed) / len(allowed) if allowed else 0.0,
        )
    return profiles


def league_average_ppg(profiles: dict[str, TeamScoringProfile]) -> float:
    """Return the league-wide average points scored per team-game."""
    if not profiles:
        return 110.0
    totals = [profile.avg_points_for for profile in profiles.values() if profile.games > 0]
    if not totals:
        return 110.0
    return sum(totals) / len(totals)


def _team_ppg(
    team: str,
    profiles: dict[str, TeamScoringProfile],
    *,
    default_ppg: float,
) -> tuple[float, float]:
    profile = profiles.get(team)
    if profile is None or profile.games == 0:
        return default_ppg, default_ppg
    return profile.avg_points_for, profile.avg_points_against


def project_points(
    home: str,
    away: str,
    profiles: dict[str, TeamScoringProfile],
    *,
    home_court_points: float = 2.5,
    default_ppg: float | None = None,
) -> tuple[float, float]:
    """Estimate each team's projected score using offensive/defensive pace blending."""
    baseline = default_ppg if default_ppg is not None else league_average_ppg(profiles)
    home_for, home_against = _team_ppg(home, profiles, default_ppg=baseline)
    away_for, away_against = _team_ppg(away, profiles, default_ppg=baseline)

    home_points = (home_for + away_against) / 2 + home_court_points / 2
    away_points = (away_for + home_against) / 2 - home_court_points / 2
    return round(home_points, 1), round(away_points, 1)


def project_game_total(
    home: str,
    away: str,
    profiles: dict[str, TeamScoringProfile],
    *,
    home_court_points: float = 2.5,
) -> dict[str, float]:
    """Return projected team scores and the combined over/under total."""
    home_points, away_points = project_points(
        home,
        away,
        profiles,
        home_court_points=home_court_points,
    )
    return {
        "home_projected_points": home_points,
        "away_projected_points": away_points,
        "projected_total": round(home_points + away_points, 1),
    }
