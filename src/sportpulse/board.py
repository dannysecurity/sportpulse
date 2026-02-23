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


def _board_title(report: dict[str, object]) -> str:
    matchups = report.get("matchups", [])
    count = len(matchups) if isinstance(matchups, list) else 0
    title = f"Board {report['date']} — {count} game(s)"
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


def format_board_table(report: dict[str, object]) -> str:
    """Render the board as a fixed-width terminal table."""
    matchups = report.get("matchups", [])
    if not isinstance(matchups, list):
        raise ValueError("report matchups must be a list")

    lines = [_board_title(report), ""]
    if not matchups:
        lines.append("No games on the board for this slate.")
        return "\n".join(lines)

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

    for index, game in enumerate(matchups, start=1):
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

    highlight_line = _format_highlights(report)
    if highlight_line:
        lines.extend(["", highlight_line])
    return "\n".join(lines)


def format_board_compact(report: dict[str, object]) -> str:
    """Render one odds-lite line per game."""
    matchups = report.get("matchups", [])
    if not isinstance(matchups, list):
        raise ValueError("report matchups must be a list")

    lines = [_board_title(report)]
    if not matchups:
        lines.append("No games on the board for this slate.")
        return "\n".join(lines)

    for index, game in enumerate(matchups, start=1):
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

    highlight_line = _format_highlights(report)
    if highlight_line:
        lines.append(highlight_line)
    return "\n".join(lines)


def format_board_csv(report: dict[str, object]) -> str:
    """Render the board as CSV for spreadsheets."""
    matchups = report.get("matchups", [])
    if not isinstance(matchups, list):
        raise ValueError("report matchups must be a list")

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
    slate_date = report.get("date", "")
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
