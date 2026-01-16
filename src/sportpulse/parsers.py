from __future__ import annotations

import csv
import json
from datetime import date
from io import StringIO
from pathlib import Path

from sportpulse.boxscore import BoxScore

_REQUIRED_KEYS = ("home", "away", "home_score", "away_score")


def parse_box_score(data: dict[str, object]) -> BoxScore:
    """Build a BoxScore from a mapping with snake_case keys."""
    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"box score missing required field(s): {joined}")

    home = data["home"]
    away = data["away"]
    home_score = data["home_score"]
    away_score = data["away_score"]
    if not isinstance(home, str) or not isinstance(away, str):
        raise ValueError("home and away must be strings")
    if not isinstance(home_score, int) or not isinstance(away_score, int):
        raise ValueError("home_score and away_score must be integers")

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


def parse_box_scores_from_csv(text: str) -> list[BoxScore]:
    """Parse historical box scores from CSV with a header row."""
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV must include a header row")

    missing = [name for name in _REQUIRED_KEYS if name not in reader.fieldnames]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"CSV header missing required column(s): {joined}")

    scores: list[BoxScore] = []
    for row_number, row in enumerate(reader, start=2):
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
                data[score_key] = int(raw_score)
            except ValueError as exc:
                raise ValueError(
                    f"CSV row {row_number}: {score_key} must be an integer"
                ) from exc

        played_on = (row.get("played_on") or "").strip()
        if played_on:
            data["played_on"] = played_on

        scores.append(parse_box_score(data))
    return scores


def load_box_scores(path: Path | str, fmt: str | None = None) -> list[BoxScore]:
    """Load historical box scores from a JSON or CSV file."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"box score file not found: {file_path}")

    resolved = (fmt or file_path.suffix.lstrip(".")).lower()
    text = file_path.read_text(encoding="utf-8")

    if resolved in ("json", "js"):
        return parse_box_scores_from_json(text)
    if resolved == "csv":
        return parse_box_scores_from_csv(text)

    raise ValueError(f"unsupported box score format: {resolved!r} (use json or csv)")


def box_scores_to_json(scores: list[BoxScore]) -> list[dict[str, object]]:
    """Serialize parsed box scores for CLI/API output."""
    return [score.summary() for score in scores]
