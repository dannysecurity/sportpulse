"""Cached loaders for schedule files and derived reports.

File-backed schedule data (matchups slates, box-score history, team schedules)
is fetched through the parsers and :mod:`sportpulse.schedule` /
:mod:`sportpulse.matchups` loaders. This module adds a second cache tier for
fully built reports so repeated CLI and API requests skip ELO replay and
projection work when source files are unchanged.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, NamedTuple

from sportpulse.matchups import build_matchups_report, load_matchups
from sportpulse.parsers import load_box_scores
from sportpulse.schedule import load_team_schedule
from sportpulse.season import build_season_report
from sportpulse.standings import build_standings_report

MatchupsReportCacheKey = tuple[
    str,
    tuple[int, int] | None,
    str,
    tuple[int, int] | None,
    str,
    float,
    float,
    float,
    float,
    bool,
    str | None,
]

SeasonReportCacheKey = tuple[
    str,
    tuple[int, int],
    str,
    str | None,
    str | None,
    str | None,
    float,
]

StandingsReportCacheKey = tuple[
    str,
    tuple[int, int],
    str | None,
    str | None,
    str,
    str | None,
]

_matchups_report_cache: dict[MatchupsReportCacheKey, dict[str, object]] = {}
_season_report_cache: dict[SeasonReportCacheKey, dict[str, object]] = {}
_standings_report_cache: dict[StandingsReportCacheKey, dict[str, object]] = {}


class FileFingerprint(NamedTuple):
    """Stable file identity for cache invalidation."""

    mtime_ns: int
    size: int


def file_fingerprint(path: Path | str) -> FileFingerprint:
    """Return mtime and size for a resolved file path."""
    resolved = Path(path).resolve()
    stat = resolved.stat()
    return FileFingerprint(stat.st_mtime_ns, stat.st_size)


def clear_schedule_report_cache() -> None:
    """Clear cached matchups, season, and standings reports."""
    _matchups_report_cache.clear()
    _season_report_cache.clear()
    _standings_report_cache.clear()


def load_matchups_report(
    matchups_file: Path | str,
    *,
    on_date: date,
    history_file: Path | str | None = None,
    history_fmt: str | None = None,
    k_factor: float = 20.0,
    home_advantage: float = 65.0,
    points_per_100_elo: float = 4.0,
    home_court_points: float = 2.5,
    advance_if_empty: bool = False,
    team: str | None = None,
) -> dict[str, object]:
    """Load a matchups slate and build an odds-lite report with caching.

    Parsed matchups and history files are cached by their loaders; this function
    additionally caches the assembled report keyed by source file fingerprints
    and report parameters.
    """
    resolved_matchups = Path(matchups_file).resolve()
    matchups_fp = file_fingerprint(resolved_matchups)
    history_fp: tuple[int, int] | None = None
    if history_file is not None:
        history_fp = file_fingerprint(history_file)

    cache_key: MatchupsReportCacheKey = (
        str(resolved_matchups),
        (matchups_fp.mtime_ns, matchups_fp.size),
        on_date.isoformat(),
        history_fp,
        history_fmt,
        k_factor,
        home_advantage,
        points_per_100_elo,
        home_court_points,
        advance_if_empty,
        team,
    )
    cached = _matchups_report_cache.get(cache_key)
    if cached is not None:
        return cached

    slate = load_matchups(resolved_matchups)
    history = (
        load_box_scores(history_file, fmt=history_fmt)
        if history_file is not None
        else None
    )
    report = build_matchups_report(
        slate,
        on_date=on_date,
        history=history,
        k_factor=k_factor,
        home_advantage=home_advantage,
        points_per_100_elo=points_per_100_elo,
        home_court_points=home_court_points,
        advance_if_empty=advance_if_empty,
        team=team,
    )
    _matchups_report_cache[cache_key] = report
    return report


def load_season_report(
    file_path: Path | str,
    team: str,
    *,
    fmt: str | None = None,
    start: date | None = None,
    end: date | None = None,
    k_factor: float = 20.0,
) -> dict[str, object]:
    """Load a team season report from a box score file with caching.

    Uses the team schedule file cache when building from disk and caches the
    final report keyed by file fingerprint, team, date range, and K-factor.
    """
    resolved = Path(file_path).resolve()
    fp = file_fingerprint(resolved)
    cache_key: SeasonReportCacheKey = (
        str(resolved),
        (fp.mtime_ns, fp.size),
        team,
        fmt,
        start.isoformat() if start is not None else None,
        end.isoformat() if end is not None else None,
        k_factor,
    )
    cached = _season_report_cache.get(cache_key)
    if cached is not None:
        return cached

    load_team_schedule(resolved, team, fmt=fmt)
    scores = load_box_scores(resolved, fmt=fmt)
    report = build_season_report(
        team,
        scores,
        start=start,
        end=end,
        k_factor=k_factor,
    )
    _season_report_cache[cache_key] = report
    return report


def load_standings_report(
    file_path: Path | str,
    *,
    fmt: str | None = None,
    start: date | None = None,
    end: date | None = None,
    tie_breaker: Literal["win_pct", "point_diff", "team_name"] = "win_pct",
) -> dict[str, object]:
    """Load a league standings report from a box score file with caching.

    Parsed box scores are cached by their loader; this function additionally
    caches the assembled standings report keyed by file fingerprint, date range,
    tie-breaker, and format.
    """
    resolved = Path(file_path).resolve()
    fp = file_fingerprint(resolved)
    cache_key: StandingsReportCacheKey = (
        str(resolved),
        (fp.mtime_ns, fp.size),
        start.isoformat() if start is not None else None,
        end.isoformat() if end is not None else None,
        tie_breaker,
        fmt,
    )
    cached = _standings_report_cache.get(cache_key)
    if cached is not None:
        return cached

    scores = load_box_scores(resolved, fmt=fmt)
    report = build_standings_report(
        scores,
        start=start,
        end=end,
        tie_breaker=tie_breaker,
    )
    _standings_report_cache[cache_key] = report
    return report
