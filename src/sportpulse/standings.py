from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Literal

from sportpulse.boxscore import BoxScore
from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, TeamStats, aggregate_team_stats
from sportpulse.stats import TeamRecord, aggregate_record, games_in_range


@dataclass(frozen=True)
class TeamStanding:
    """League-table row for one team."""

    team: str
    stats: TeamStats

    @property
    def record(self) -> TeamRecord:
        return self.stats.record

    @property
    def win_pct(self) -> float:
        return self.stats.record.win_pct

    @property
    def point_differential(self) -> int:
        return self.stats.point_differential


@dataclass(frozen=True)
class VenueSplit:
    """Win/loss record split by home and away appearances."""

    home: TeamRecord
    away: TeamRecord

    @property
    def combined(self) -> TeamRecord:
        return self.home + self.away


def discover_teams(games: Iterable[GameResult]) -> frozenset[str]:
    """Collect every team name that appears as home or away."""
    names: set[str] = set()
    for game in games:
        names.add(game.home)
        names.add(game.away)
    return frozenset(names)


def aggregate_standings(
    games: Iterable[GameResult],
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, TeamStats]:
    """Roll up stats for every team discovered in ``games``."""
    game_list = list(games)
    if start is not None and end is not None:
        scoped_games = games_in_range(game_list, start, end)
    else:
        scoped_games = game_list
    teams = discover_teams(scoped_games)
    return {
        team: aggregate_team_stats(
            team,
            game_list,
            policy=policy,
            start=start,
            end=end,
        )
        for team in teams
    }


def rank_standings(
    standings: dict[str, TeamStats],
    *,
    tie_breaker: Literal["win_pct", "point_diff", "team_name"] = "win_pct",
) -> list[TeamStanding]:
    """Sort teams for a league table with deterministic tie-breaking."""
    rows = [TeamStanding(team=team, stats=stats) for team, stats in standings.items()]

    def sort_key(row: TeamStanding) -> tuple:
        primary = -row.win_pct if tie_breaker == "win_pct" else -row.point_differential
        secondary = -row.point_differential
        tertiary = row.team
        if tie_breaker == "point_diff":
            return (-row.point_differential, -row.win_pct, tertiary)
        if tie_breaker == "team_name":
            return (tertiary,)
        return (primary, secondary, tertiary)

    return sorted(rows, key=sort_key)


def head_to_head_record(
    team: str,
    opponent: str,
    games: Iterable[GameResult],
) -> TeamRecord:
    """Record for ``team`` in games where ``opponent`` is the other participant."""
    matchups = [
        game
        for game in games
        if game.involves(team) and game.involves(opponent) and team != opponent
    ]
    return aggregate_record(team, matchups)


def venue_split(team: str, games: Iterable[GameResult]) -> VenueSplit:
    """Split a team's record by home and away appearances."""
    home_games = [game for game in games if game.home == team]
    away_games = [game for game in games if game.away == team]
    return VenueSplit(
        home=aggregate_record(team, home_games),
        away=aggregate_record(team, away_games),
    )


def standings_in_range(
    games: Iterable[GameResult],
    start: date,
    end: date,
    *,
    policy: ParticipationPolicy = ParticipationPolicy.PARTICIPANT_ONLY,
) -> dict[str, TeamStats]:
    """Convenience wrapper for date-filtered league standings."""
    return aggregate_standings(games, policy=policy, start=start, end=end)


def games_for_teams(
    games: Iterable[GameResult],
    teams: Iterable[str],
) -> list[GameResult]:
    """Return games where at least one listed team participates."""
    team_set = frozenset(teams)
    return [
        game
        for game in games
        if game.home in team_set or game.away in team_set
    ]


def build_standings_report(
    scores: list[BoxScore],
    *,
    start: date | None = None,
    end: date | None = None,
    tie_breaker: Literal["win_pct", "point_diff", "team_name"] = "win_pct",
) -> dict[str, object]:
    """Build a ranked league table from parsed box scores."""
    games = [box.to_result() for box in scores]
    table = aggregate_standings(games, start=start, end=end)
    ranked = rank_standings(table, tie_breaker=tie_breaker)

    if start is not None and end is not None:
        games_counted = len(games_in_range(games, start, end))
    else:
        games_counted = len(games)

    rows: list[dict[str, object]] = []
    for rank, row in enumerate(ranked, start=1):
        rows.append(
            {
                "rank": rank,
                "team": row.team,
                "record": row.record.to_dict(),
                "win_pct": round(row.win_pct, 3),
                "point_differential": row.point_differential,
                "avg_margin": round(row.stats.avg_margin, 1),
            }
        )

    report: dict[str, object] = {
        "games_counted": games_counted,
        "tie_breaker": tie_breaker,
        "standings": rows,
    }
    if start is not None and end is not None:
        report["start_date"] = start.isoformat()
        report["end_date"] = end.isoformat()
    return report


def format_standings_table(report: dict[str, object]) -> str:
    """Render a standings report as a fixed-width terminal table."""
    standings = report.get("standings", [])
    if not isinstance(standings, list):
        raise ValueError("report standings must be a list")

    games = report.get("games_counted", 0)
    title = f"League standings — {games} game(s)"
    lines = [title, ""]
    if not standings:
        lines.append("No games to rank.")
        return "\n".join(lines)

    header = f"{'RK':>3} {'TEAM':<16} {'W-L-T':>7} {'PCT':>6} {'DIFF':>6} {'AVG':>6}"
    lines.extend([header, "-" * len(header)])
    for row in standings:
        if not isinstance(row, dict):
            continue
        record = row.get("record", {})
        if not isinstance(record, dict):
            continue
        wins = record.get("wins", 0)
        losses = record.get("losses", 0)
        ties = record.get("ties", 0)
        wlt = f"{wins}-{losses}-{ties}"
        win_pct = row.get("win_pct", 0.0)
        diff = row.get("point_differential", 0)
        avg = row.get("avg_margin", 0.0)
        lines.append(
            f"{row['rank']:>3} {row['team']:<16} {wlt:>7} "
            f"{win_pct:>6.3f} {diff:>+6d} {avg:>+6.1f}"
        )
    return "\n".join(lines)
