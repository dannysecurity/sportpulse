from __future__ import annotations

import csv
from io import StringIO

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.box_score import parse_box_score
from sportpulse.parsers.schema import REQUIRED_FIELDS, normalize_csv_headers


def _strip_utf8_bom(text: str) -> str:
    """Remove a leading UTF-8 BOM from exported spreadsheet files."""
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def _csv_row_is_blank(row: dict[str, str | None]) -> bool:
    """Return True when every CSV cell is empty or whitespace."""
    return all((value or "").strip() == "" for value in row.values())


def parse_box_scores_from_csv(text: str) -> list[BoxScore]:
    """Parse historical box scores from CSV with a header row.

    Header columns may use canonical names or common historical export aliases
    such as ``home_team``, ``away_pts``, or ``game_date``.
    """
    reader = csv.DictReader(StringIO(_strip_utf8_bom(text)))
    if reader.fieldnames is None:
        raise ValueError("CSV must include a header row")

    header_map = normalize_csv_headers(list(reader.fieldnames))
    canonical_headers = set(header_map.values())
    missing = [name for name in REQUIRED_FIELDS if name not in canonical_headers]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"CSV header missing required column(s): {joined}")

    scores: list[BoxScore] = []
    for row_number, row in enumerate(reader, start=2):
        if _csv_row_is_blank(row):
            continue

        data: dict[str, object] = {}
        for original_header, canonical in header_map.items():
            raw_value = row.get(original_header)
            if raw_value is None:
                continue
            stripped = raw_value.strip()
            if not stripped and canonical in REQUIRED_FIELDS:
                continue
            data[canonical] = stripped if stripped else None

        if not data.get("home") or not data.get("away"):
            raise ValueError(f"CSV row {row_number}: home and away are required")

        for score_key in ("home_score", "away_score"):
            if score_key not in data or data[score_key] in (None, ""):
                raise ValueError(f"CSV row {row_number}: {score_key} is required")

        try:
            scores.append(parse_box_score(data))
        except ValueError as exc:
            message = str(exc)
            if message.startswith("CSV row"):
                raise
            raise ValueError(f"CSV row {row_number}: {message}") from exc

    return scores
