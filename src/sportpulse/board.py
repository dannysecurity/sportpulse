"""Game-day odds-lite board for today's matchups and projections."""

from __future__ import annotations

import csv
import io
from typing import Literal

BoardSort = Literal["spread", "confidence", "total", "matchup", "time"]
BoardFormat = Literal["json", "table", "compact", "csv"]
ConfidenceTier = Literal["toss_up", "lean", "strong"]

SORT_OPTIONS: tuple[BoardSort, ...] = ("spread", "confidence", "total", "matchup", "time")
FORMAT_OPTIONS: tuple[BoardFormat, ...] = ("json", "table", "compact", "csv")

_TOSS_UP_SPREAD = 2.0
_STRONG_SPREAD = 6.0
_CONFIDENCE_RANK = {"toss_up": 0, "lean": 1, "strong": 2}


def spread_magnitude(game: dict[str, object]) -> float:
    """Return the absolute home spread, or zero when missing."""
    spread = game.get("home_spread")
    if not isinstance(spread, (int, float)):
        return 0.0
    return abs(float(spread))


def favorite_side(game: dict[str, object]) -> str:
    """Return ``home``, ``away``, or ``pick_em`` based on the model spread."""
    spread = game.get("home_spread")
    if not isinstance(spread, (int, float)):
        return "pick_em"
    if spread < 0:
        return "home"
    if spread > 0:
        return "away"
    return "pick_em"


def classify_confidence(
    game: dict[str, object],
    *,
    toss_up_threshold: float = _TOSS_UP_SPREAD,
    strong_threshold: float = _STRONG_SPREAD,
) -> ConfidenceTier:
    """Bucket a projection by spread magnitude."""
    magnitude = spread_magnitude(game)
    if magnitude < toss_up_threshold:
        return "toss_up"
    if magnitude >= strong_threshold:
        return "strong"
    return "lean"


def board_pick_label(game: dict[str, object]) -> str:
    """Render a short pick line such as ``Celtics -4.5``."""
    spread = game.get("home_spread")
    home = game.get("home")
    away = game.get("away")
    if not isinstance(home, str) or not isinstance(away, str):
        return "pick'em"
    if not isinstance(spread, (int, float)):
        return "pick'em"
    if spread == 0:
        return "pick'em"
    favorite = home if spread < 0 else away
    line = abs(float(spread))
    return f"{favorite} -{line:.1f}"


def annotate_board_game(
    game: dict[str, object],
    *,
    toss_up_threshold: float = _TOSS_UP_SPREAD,
    strong_threshold: float = _STRONG_SPREAD,
) -> dict[str, object]:
    """Attach board metadata to a projected matchup."""
    annotated = dict(game)
    side = favorite_side(game)
    home = game.get("home")
    away = game.get("away")
    favorite_team: str | None
    if side == "home" and isinstance(home, str):
        favorite_team = home
    elif side == "away" and isinstance(away, str):
        favorite_team = away
    else:
        favorite_team = None

    confidence = classify_confidence(
        game,
        toss_up_threshold=toss_up_threshold,
        strong_threshold=strong_threshold,
    )
    annotated["board_favorite"] = favorite_team
    annotated["board_spread_magnitude"] = round(spread_magnitude(game), 1)
    annotated["board_confidence"] = confidence
    annotated["board_pick"] = board_pick_label(game)
    return annotated


def sort_board_games(games: list[dict[str, object]], sort_by: BoardSort) -> list[dict[str, object]]:
    """Return a new list sorted for terminal display."""
    if sort_by == "matchup":
        return sorted(
            games,
            key=lambda game: (
                str(game.get("away", "")),
                str(game.get("home", "")),
            ),
        )
    if sort_by == "time":
        return sorted(
            games,
            key=lambda game: (
                str(game.get("start_time") or "99:99"),
                str(game.get("away", "")),
            ),
        )
    if sort_by == "total":
        return sorted(
            games,
            key=lambda game: float(game.get("projected_total") or 0.0),
            reverse=True,
        )
    if sort_by == "confidence":
        return sorted(
            games,
            key=lambda game: (
                _CONFIDENCE_RANK.get(str(game.get("board_confidence")), 0),
                spread_magnitude(game),
            ),
            reverse=True,
        )
    return sorted(games, key=spread_magnitude, reverse=True)


def filter_board_games(
    games: list[dict[str, object]],
    *,
    min_spread: float | None = None,
    confidence: ConfidenceTier | None = None,
) -> list[dict[str, object]]:
    """Drop games that do not meet optional board filters."""
    filtered = games
    if min_spread is not None:
        filtered = [
            game for game in filtered if spread_magnitude(game) >= min_spread
        ]
    if confidence is not None:
        filtered = [
            game
            for game in filtered
            if game.get("board_confidence") == confidence
        ]
    return filtered


def build_board_highlights(games: list[dict[str, object]]) -> dict[str, object]:
    """Summarize notable odds-lite lines across the slate."""
    if not games:
        return {
            "strongest_favorite": None,
            "closest_game": None,
            "highest_total": None,
            "confidence_counts": {"toss_up": 0, "lean": 0, "strong": 0},
        }

    strongest = max(games, key=spread_magnitude)
    closest = min(games, key=spread_magnitude)
    totals = [
        game
        for game in games
        if isinstance(game.get("projected_total"), (int, float))
    ]
    highest_total = max(totals, key=lambda game: float(game["projected_total"])) if totals else None

    counts = {"toss_up": 0, "lean": 0, "strong": 0}
    for game in games:
        tier = game.get("board_confidence")
        if tier in counts:
            counts[tier] += 1

    def _label(game: dict[str, object] | None) -> str | None:
        if game is None:
            return None
        away = game.get("away")
        home = game.get("home")
        if isinstance(away, str) and isinstance(home, str):
            return f"{away} @ {home}"
        return None

    return {
        "strongest_favorite": _label(strongest),
        "strongest_pick": strongest.get("board_pick"),
        "closest_game": _label(closest),
        "closest_pick": closest.get("board_pick"),
        "highest_total": _label(highest_total),
        "highest_total_value": highest_total.get("projected_total") if highest_total else None,
        "confidence_counts": counts,
    }


def _annotate_and_filter_games(
    raw_matchups: list[object],
    *,
    sort_by: BoardSort,
    min_spread: float | None,
    confidence: ConfidenceTier | None,
    toss_up_threshold: float,
    strong_threshold: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return (annotated_games, sorted_filtered_games) for board rendering."""
    annotated = [
        annotate_board_game(
            game,
            toss_up_threshold=toss_up_threshold,
            strong_threshold=strong_threshold,
        )
        for game in raw_matchups
        if isinstance(game, dict)
    ]
    filtered = filter_board_games(
        annotated,
        min_spread=min_spread,
        confidence=confidence,
    )
    sorted_games = sort_board_games(filtered, sort_by)
    return annotated, sorted_games


def build_board_report(
    matchups_report: dict[str, object],
    *,
    sort_by: BoardSort = "spread",
    min_spread: float | None = None,
    confidence: ConfidenceTier | None = None,
    toss_up_threshold: float = _TOSS_UP_SPREAD,
    strong_threshold: float = _STRONG_SPREAD,
) -> dict[str, object]:
    """Transform a matchups report into a sorted game-day board."""
    raw_matchups = matchups_report.get("matchups", [])
    if not isinstance(raw_matchups, list):
        raise ValueError("report matchups must be a list")

    annotated, sorted_games = _annotate_and_filter_games(
        raw_matchups,
        sort_by=sort_by,
        min_spread=min_spread,
        confidence=confidence,
        toss_up_threshold=toss_up_threshold,
        strong_threshold=strong_threshold,
    )

    board: dict[str, object] = dict(matchups_report)
    board["matchups"] = sorted_games
    board["board"] = {
        "sort": sort_by,
        "min_spread": min_spread,
        "confidence_filter": confidence,
        "highlights": build_board_highlights(sorted_games),
        "games_shown": len(sorted_games),
        "games_total": len(annotated),
    }
    return board


def build_multi_day_board_report(
    matchups_report: dict[str, object],
    *,
    sort_by: BoardSort = "spread",
    min_spread: float | None = None,
    confidence: ConfidenceTier | None = None,
    toss_up_threshold: float = _TOSS_UP_SPREAD,
    strong_threshold: float = _STRONG_SPREAD,
) -> dict[str, object]:
    """Transform a multi-day matchups report into board-annotated daily slates."""
    slates = matchups_report.get("slates")
    if not isinstance(slates, list):
        raise ValueError("report slates must be a list")

    board_slates: list[dict[str, object]] = []
    all_shown: list[dict[str, object]] = []
    games_total = 0

    for slate in slates:
        if not isinstance(slate, dict):
            continue
        raw_matchups = slate.get("matchups", [])
        if not isinstance(raw_matchups, list):
            continue
        annotated, sorted_games = _annotate_and_filter_games(
            raw_matchups,
            sort_by=sort_by,
            min_spread=min_spread,
            confidence=confidence,
            toss_up_threshold=toss_up_threshold,
            strong_threshold=strong_threshold,
        )
        games_total += len(annotated)
        all_shown.extend(sorted_games)
        board_slates.append(
            {
                "date": slate.get("date", ""),
                "matchups": sorted_games,
                "summary": slate.get("summary", {}),
                "board": {
                    "games_shown": len(sorted_games),
                    "games_total": len(annotated),
                },
            }
        )

    report: dict[str, object] = dict(matchups_report)
    report["slates"] = board_slates
    report["board"] = {
        "sort": sort_by,
        "min_spread": min_spread,
        "confidence_filter": confidence,
        "highlights": build_board_highlights(all_shown),
        "games_shown": len(all_shown),
        "games_total": games_total,
    }
    return report


def build_today_board_report(
    matchups_report: dict[str, object],
    *,
    sort_by: BoardSort = "time",
    min_spread: float | None = None,
    confidence: ConfidenceTier | None = None,
    toss_up_threshold: float = _TOSS_UP_SPREAD,
    strong_threshold: float = _STRONG_SPREAD,
) -> dict[str, object]:
    """Build a today-style board from a single- or multi-day matchups report."""
    if "slates" in matchups_report:
        report = build_multi_day_board_report(
            matchups_report,
            sort_by=sort_by,
            min_spread=min_spread,
            confidence=confidence,
            toss_up_threshold=toss_up_threshold,
            strong_threshold=strong_threshold,
        )
    else:
        report = build_board_report(
            matchups_report,
            sort_by=sort_by,
            min_spread=min_spread,
            confidence=confidence,
            toss_up_threshold=toss_up_threshold,
            strong_threshold=strong_threshold,
        )
    report["title_label"] = "Today"
    return report


def _append_slate_banner(title: str, report: dict[str, object]) -> str:
    if report.get("advanced_to_next_slate"):
        requested = report.get("requested_date")
        if isinstance(requested, str):
            return f"{title}  (requested {requested}, next slate)"
    if report.get("advanced_to_last_slate"):
        requested = report.get("requested_date")
        if isinstance(requested, str):
            return f"{title}  (requested {requested}, last slate)"
    return title


def _board_label(report: dict[str, object]) -> str:
    label = report.get("title_label", "Board")
    if not isinstance(label, str) or not label:
        return "Board"
    return label


def _board_title(report: dict[str, object]) -> str:
    matchups = report.get("matchups", [])
    count = len(matchups) if isinstance(matchups, list) else 0
    label = _board_label(report)
    title = f"{label} {report['date']} — {count} game(s)"
    title = _append_slate_banner(title, report)
    team_filter = report.get("team_filter")
    if isinstance(team_filter, str):
        title = f"{title}  [{team_filter}]"
    return title


def _multi_day_board_title(report: dict[str, object]) -> str:
    summary = report.get("summary")
    games = summary.get("games", 0) if isinstance(summary, dict) else 0
    start = report.get("start_date", "")
    end = report.get("end_date", "")
    days = report.get("days", 1)
    label = _board_label(report)
    title = f"{label} {start} — {end} ({days} days) — {games} game(s)"
    title = _append_slate_banner(title, report)
    team_filter = report.get("team_filter")
    if isinstance(team_filter, str):
        title = f"{title}  [{team_filter}]"
    return title


def _format_highlights(report: dict[str, object]) -> str:
    board = report.get("board")
    if not isinstance(board, dict):
        return ""
    highlights = board.get("highlights")
    if not isinstance(highlights, dict):
        return ""

    parts: list[str] = []
    counts = highlights.get("confidence_counts")
    if isinstance(counts, dict):
        parts.append(
            f"{counts.get('strong', 0)} strong / {counts.get('lean', 0)} lean / "
            f"{counts.get('toss_up', 0)} toss-up"
        )
    if highlights.get("strongest_pick"):
        parts.append(f"top line: {highlights['strongest_pick']}")
    if highlights.get("closest_pick"):
        parts.append(f"closest: {highlights['closest_pick']}")
    if highlights.get("highest_total_value") is not None:
        parts.append(f"top O/U: {highlights['highest_total_value']}")
    if not parts:
        return ""
    return "Highlights: " + ", ".join(parts)


def _format_moneyline(value: object) -> str:
    if not isinstance(value, int):
        return str(value)
    return f"+{value}" if value > 0 else str(value)


def _confidence_badge(tier: object) -> str:
    if tier == "strong":
        return "STR"
    if tier == "lean":
        return "LN "
    if tier == "toss_up":
        return "TOU"
    return "---"


def _format_window_summary(summary: dict[str, object]) -> str:
    """Render a one-line digest for a multi-day odds-lite window."""
    games = summary.get("games", 0)
    if not isinstance(games, int) or games == 0:
        return ""

    days = summary.get("days", 0)
    days_with_games = summary.get("days_with_games", 0)
    parts = [f"{days_with_games}/{days} days with games"]
    parts.append(f"{summary['home_favorites']} home fav")
    parts.append(f"{summary['away_favorites']} away fav")
    if summary.get("pick_em_games"):
        parts.append(f"{summary['pick_em_games']} pick'em")
    if summary.get("has_scoring_projections") and summary.get("avg_projected_total") is not None:
        parts.append(f"avg O/U {summary['avg_projected_total']}")
    return "Window: " + ", ".join(parts)


def _append_board_table_rows(
    lines: list[str],
    matchups: list[object],
    *,
    start_index: int = 1,
) -> int:
    """Append board table rows and return the next game index."""
    if not matchups:
        lines.append("No games on the board for this slate.")
        return start_index

    show_totals = any(
        isinstance(game, dict) and "projected_total" in game for game in matchups
    )
    show_time = any(
        isinstance(game, dict) and game.get("start_time") for game in matchups
    )
    if show_totals:
        header = (
            f"{'#':>2} {'MATCHUP':<22} {'PICK':<16} {'CONF':>4} {'SPREAD':>7} "
            f"{'HOME%':>6} {'AWAY%':>6} {'O/U':>6}"
        )
    else:
        header = (
            f"{'#':>2} {'MATCHUP':<22} {'PICK':<16} {'CONF':>4} {'SPREAD':>7} "
            f"{'HOME%':>6} {'AWAY%':>6}"
        )
    if show_time:
        header = f"{'TIME':>5} {header}"
    lines.extend([header, "-" * len(header)])

    index = start_index
    for game in matchups:
        if not isinstance(game, dict):
            continue
        label = f"{game['away']} @ {game['home']}"
        spread = game.get("home_spread")
        spread_text = f"{spread:+.1f}" if isinstance(spread, (int, float)) else str(spread)
        home_pct = f"{float(game['home_win_prob']) * 100:.0f}%"
        away_pct = f"{float(game['away_win_prob']) * 100:.0f}%"
        pick = str(game.get("board_pick", "pick'em"))
        conf = _confidence_badge(game.get("board_confidence"))
        row = (
            f"{index:>2} {label:<22} {pick:<16} {conf:>4} {spread_text:>7} "
            f"{home_pct:>6} {away_pct:>6}"
        )
        if show_totals:
            total = game.get("projected_total", "-")
            total_text = f"{total:.1f}" if isinstance(total, (int, float)) else str(total)
            row = f"{row} {total_text:>6}"
        if show_time:
            start = str(game.get("start_time") or "--:--")
            row = f"{start:>5} {row}"
        lines.append(row)
        index += 1
    return index


def format_board_table(report: dict[str, object]) -> str:
    """Render the board as a fixed-width terminal table."""
    if "slates" in report:
        return _format_multi_day_board_table(report)

    matchups = report.get("matchups", [])
    if not isinstance(matchups, list):
        raise ValueError("report matchups must be a list")

    lines = [_board_title(report), ""]
    _append_board_table_rows(lines, matchups)

    highlight_line = _format_highlights(report)
    if highlight_line:
        lines.extend(["", highlight_line])
    return "\n".join(lines)


def _format_multi_day_board_table(report: dict[str, object]) -> str:
    slates = report.get("slates")
    if not isinstance(slates, list):
        raise ValueError("report slates must be a list")

    lines = [_multi_day_board_title(report), ""]
    if not slates:
        lines.append("No games on the board for this window.")
        return "\n".join(lines)

    game_number = 1
    for index, slate in enumerate(slates):
        if not isinstance(slate, dict):
            continue
        matchups = slate.get("matchups", [])
        if not isinstance(matchups, list):
            continue
        if index > 0:
            lines.append("")
        slate_date = slate.get("date", "")
        lines.append(f"--- {slate_date} ---")
        game_number = _append_board_table_rows(
            lines,
            matchups,
            start_index=game_number,
        )

    highlight_line = _format_highlights(report)
    summary = report.get("summary")
    footer_parts: list[str] = []
    if highlight_line:
        footer_parts.append(highlight_line)
    if isinstance(summary, dict) and summary.get("games"):
        window_line = _format_window_summary(summary)
        if window_line:
            footer_parts.append(window_line)
    if footer_parts:
        lines.extend(["", *footer_parts])
    return "\n".join(lines)


def _append_board_compact_lines(
    lines: list[str],
    matchups: list[object],
    *,
    start_index: int = 1,
) -> int:
    index = start_index
    for game in matchups:
        if not isinstance(game, dict):
            continue
        label = f"{game['away']} @ {game['home']}"
        pick = game.get("board_pick", "pick'em")
        conf = game.get("board_confidence", "lean")
        home_ml = _format_moneyline(game.get("home_moneyline"))
        away_ml = _format_moneyline(game.get("away_moneyline"))
        line = f"{index}. {label} | {pick} ({conf}) | ML {home_ml}/{away_ml}"
        total = game.get("projected_total")
        if isinstance(total, (int, float)):
            line = f"{line} | O/U {total:.1f}"
        start = game.get("start_time")
        if isinstance(start, str) and start:
            line = f"{start} {line}"
        lines.append(line)
        index += 1
    return index


def format_board_compact(report: dict[str, object]) -> str:
    """Render one odds-lite line per game."""
    if "slates" in report:
        return _format_multi_day_board_compact(report)

    matchups = report.get("matchups", [])
    if not isinstance(matchups, list):
        raise ValueError("report matchups must be a list")

    lines = [_board_title(report)]
    if not matchups:
        lines.append("No games on the board for this slate.")
        return "\n".join(lines)

    _append_board_compact_lines(lines, matchups)

    highlight_line = _format_highlights(report)
    if highlight_line:
        lines.append(highlight_line)
    return "\n".join(lines)


def _format_multi_day_board_compact(report: dict[str, object]) -> str:
    slates = report.get("slates")
    if not isinstance(slates, list):
        raise ValueError("report slates must be a list")

    lines = [_multi_day_board_title(report)]
    if not slates:
        lines.append("No games on the board for this window.")
        return "\n".join(lines)

    game_number = 1
    for slate in slates:
        if not isinstance(slate, dict):
            continue
        matchups = slate.get("matchups", [])
        if not isinstance(matchups, list) or not matchups:
            continue
        slate_date = slate.get("date", "")
        lines.append(f"--- {slate_date} ---")
        game_number = _append_board_compact_lines(
            lines,
            matchups,
            start_index=game_number,
        )

    highlight_line = _format_highlights(report)
    if highlight_line:
        lines.append(highlight_line)
    summary = report.get("summary")
    if isinstance(summary, dict) and summary.get("games"):
        window_line = _format_window_summary(summary)
        if window_line:
            lines.append(window_line)
    return "\n".join(lines)


def _write_board_csv_rows(
    writer: csv.writer,
    slate_date: str,
    matchups: list[object],
) -> None:
    for game in matchups:
        if not isinstance(game, dict):
            continue
        writer.writerow(
            [
                slate_date,
                game.get("start_time", ""),
                game.get("away", ""),
                game.get("home", ""),
                game.get("board_pick", ""),
                game.get("board_confidence", ""),
                game.get("home_spread", ""),
                game.get("home_win_prob", ""),
                game.get("away_win_prob", ""),
                game.get("home_moneyline", ""),
                game.get("away_moneyline", ""),
                game.get("projected_total", ""),
            ]
        )


def format_board_csv(report: dict[str, object]) -> str:
    """Render the board as CSV for spreadsheets."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "date",
            "start_time",
            "away",
            "home",
            "board_pick",
            "board_confidence",
            "home_spread",
            "home_win_prob",
            "away_win_prob",
            "home_moneyline",
            "away_moneyline",
            "projected_total",
        ]
    )

    if "slates" in report:
        slates = report.get("slates")
        if not isinstance(slates, list):
            raise ValueError("report slates must be a list")
        for slate in slates:
            if not isinstance(slate, dict):
                continue
            matchups = slate.get("matchups", [])
            if not isinstance(matchups, list):
                continue
            _write_board_csv_rows(writer, str(slate.get("date", "")), matchups)
    else:
        matchups = report.get("matchups", [])
        if not isinstance(matchups, list):
            raise ValueError("report matchups must be a list")
        _write_board_csv_rows(writer, str(report.get("date", "")), matchups)

    return buffer.getvalue().rstrip("\n")


def format_board_report(report: dict[str, object], fmt: BoardFormat) -> str:
    """Dispatch board formatting to the requested output type."""
    if fmt == "table":
        return format_board_table(report)
    if fmt == "compact":
        return format_board_compact(report)
    if fmt == "csv":
        return format_board_csv(report)
    raise ValueError(f"unsupported board format: {fmt}")
