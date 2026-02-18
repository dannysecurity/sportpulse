from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.models import GameResult
from sportpulse.parsers import load_box_scores
from sportpulse.rollup import ParticipationPolicy, TeamStats, aggregate_team_stats
from sportpulse.stats import (
    aggregate_record,
    aggregate_record_in_range,
    games_in_range,
    point_differential,
    point_differential_in_range,
)

_schedule_cache: dict[tuple[str, str], tuple[int, int, Schedule]] = {}


def clear_schedule_cache() -> None:
    """Clear the in-process team schedule file cache."""
    _schedule_cache.clear()


def schedule_from_scores(team: str, scores: list[BoxScore]) -> Schedule:
    """Build a team schedule from parsed box scores."""
    schedule = Schedule(team=team)
    for box in scores:
        if box.home == team or box.away == team:
            schedule.add(box.to_result())
    return schedule


def load_team_schedule(path: Path | str, team: str, *, fmt: str | None = None) -> Schedule:
    """Load a team's schedule from a box score file.

    Built schedules are cached in-process keyed by resolved path, team, and
    file modification time so repeated loads skip disk I/O and rebuilding.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"box score file not found: {file_path}")

    resolved_path = file_path.resolve()
    stat = resolved_path.stat()
    cache_key = (str(resolved_path), team)
    cached = _schedule_cache.get(cache_key)
    if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]

    schedule = schedule_from_scores(team, load_box_scores(resolved_path, fmt=fmt))
    _schedule_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, schedule)
    return schedule


@dataclass
class Schedule:
    """Team schedule with date-range filtering."""

    team: str
    games: list[GameResult] = field(default_factory=list)

    def add(self, game: GameResult) -> None:
        if game.home != self.team and game.away != self.team:
            raise ValueError(f"{self.team} is not a participant in {game}")
        self.games.append(game)

    def between(self, start: date, end: date) -> list[GameResult]:
        return games_in_range(self.games, start, end)

    def record(self) -> dict[str, int]:
        return aggregate_record(self.team, self.games).to_dict()

    def record_in_range(self, start: date, end: date) -> dict[str, int]:
        return aggregate_record_in_range(self.team, self.games, start, end).to_dict()

    def point_diff(self) -> int:
        return point_differential(self.team, self.games)

    def point_diff_in_range(self, start: date, end: date) -> int:
        return point_differential_in_range(self.team, self.games, start, end)

    def team_stats(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> TeamStats:
        return aggregate_team_stats(
            self.team,
            self.games,
            policy=ParticipationPolicy.PARTICIPANT_ONLY,
            start=start,
            end=end,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "team": self.team,
            "games": [
                {
                    "home": g.home,
                    "away": g.away,
                    "home_score": g.home_score,
                    "away_score": g.away_score,
                    "played_on": g.played_on.isoformat() if g.played_on else None,
                }
                for g in self.games
            ],
            "record": self.record(),
        }
