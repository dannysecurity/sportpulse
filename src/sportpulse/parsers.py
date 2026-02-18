from __future__ import annotations

import csv
import json
from datetime import date
from io import StringIO
from pathlib import Path

from sportpulse.boxscore import BoxScore

_REQUIRED_KEYS = ("home", "away", "home_score", "away_score")
_box_score_cache: dict[tuple[str, str | None], tuple[int, int, list[BoxScore]]] = {}


def _coerce_score(value: object, field: str) -> int:
    """Normalize a score value from JSON, CSV, or API payloads."""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{field} must be an integer")
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field} must be an integer")
        try:
            numeric = float(stripped)
        except ValueError as exc:
            raise ValueError(f"{field} must be an integer") from exc
        if not numeric.is_integer():
            raise ValueError(f"{field} must be an integer")
        return int(numeric)
    raise ValueError(f"{field} must be an integer")


def parse_box_score(data: dict[str, object]) -> BoxScore:
    """Build a BoxScore from a mapping with snake_case keys."""
    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"box score missing required field(s): {joined}")

    home = data["home"]
    away = data["away"]
    if not isinstance(home, str) or not isinstance(away, str):
        raise ValueError("home and away must be strings")
    home = home.strip()
    away = away.strip()
    if not home or not away:
        raise ValueError("home and away must be non-empty strings")
    home_score = _coerce_score(data["home_score"], "home_score")
    away_score = _coerce_score(data["away_score"], "away_score")

    played_on: date | None = None
    if "played_on" in data and data["played_on"] is not None:
        raw_date = data["played_on"]
        if isinstance(raw_date, date):
            played_on = raw_date
        elif isinstance(raw_date, str):
            try:
                played_on = date.fromisoformat(raw_date)
            except ValueError as exc:
                raise ValueError(f"invalid played_on date: {raw_date!r}") from exc
        else:
            raise ValueError("played_on must be an ISO date string or null")

    return BoxScore(
        home=home,
        away=away,
        home_score=home_score,
        away_score=away_score,
        played_on=played_on,
    )


def parse_box_scores_from_json(text: str) -> list[BoxScore]:
    """Parse historical box scores from JSON text.

    Accepts a single game object, a list of games, or a schedule-style
    wrapper with a top-level ``games`` array (matching ``Schedule.to_json``).
    """
    payload = json.loads(text)
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and "games" in payload:
        games = payload["games"]
        if not isinstance(games, list):
            raise ValueError("games must be a list when present")
        records = games
    elif isinstance(payload, dict):
        records = [payload]
    else:
        raise ValueError("JSON must be an object, a list of objects, or a schedule wrapper")

    scores: list[BoxScore] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"game at index {index} must be an object")
        scores.append(parse_box_score(record))
    return scores


def _strip_utf8_bom(text: str) -> str:
    """Remove a leading UTF-8 BOM from exported spreadsheet files."""
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def _csv_row_is_blank(row: dict[str, str | None]) -> bool:
    """Return True when every CSV cell is empty or whitespace."""
    return all((value or "").strip() == "" for value in row.values())


def parse_box_scores_from_csv(text: str) -> list[BoxScore]:
    """Parse historical box scores from CSV with a header row."""
    reader = csv.DictReader(StringIO(_strip_utf8_bom(text)))
    if reader.fieldnames is None:
        raise ValueError("CSV must include a header row")

    missing = [name for name in _REQUIRED_KEYS if name not in reader.fieldnames]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"CSV header missing required column(s): {joined}")

    scores: list[BoxScore] = []
    for row_number, row in enumerate(reader, start=2):
        if _csv_row_is_blank(row):
            continue

        data: dict[str, object] = {
            "home": (row.get("home") or "").strip(),
            "away": (row.get("away") or "").strip(),
        }
        if not data["home"] or not data["away"]:
            raise ValueError(f"CSV row {row_number}: home and away are required")

        for score_key in ("home_score", "away_score"):
            raw_score = (row.get(score_key) or "").strip()
            if not raw_score:
                raise ValueError(f"CSV row {row_number}: {score_key} is required")
            try:
                data[score_key] = _coerce_score(raw_score, score_key)
            except ValueError as exc:
                raise ValueError(
                    f"CSV row {row_number}: {score_key} must be an integer"
                ) from exc

        played_on = (row.get("played_on") or "").strip()
        if played_on:
            data["played_on"] = played_on

        scores.append(parse_box_score(data))
    return scores


def clear_box_score_cache() -> None:
    """Clear the in-process box score file cache."""
    _box_score_cache.clear()


def _read_box_scores(file_path: Path, fmt: str | None) -> list[BoxScore]:
    resolved = (fmt or file_path.suffix.lstrip(".")).lower()
    text = file_path.read_text(encoding="utf-8")

    if resolved in ("json", "js"):
        return parse_box_scores_from_json(text)
    if resolved == "csv":
        return parse_box_scores_from_csv(text)

    raise ValueError(f"unsupported box score format: {resolved!r} (use json or csv)")


def load_box_scores(path: Path | str, fmt: str | None = None) -> list[BoxScore]:
    """Load historical box scores from a JSON or CSV file.

    Parsed results are cached in-process keyed by resolved path, format, and
    file modification time so repeated loads skip disk I/O and parsing.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"box score file not found: {file_path}")

    resolved_path = file_path.resolve()
    stat = resolved_path.stat()
    cache_key = (str(resolved_path), fmt)
    cached = _box_score_cache.get(cache_key)
    if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]

    scores = _read_box_scores(resolved_path, fmt)
    _box_score_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, scores)
    return scores


def box_scores_to_json(scores: list[BoxScore]) -> list[dict[str, object]]:
    """Serialize parsed box scores for CLI/API output."""
    return [score.summary() for score in scores]
