from __future__ import annotations

import json

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.box_score import parse_box_score


def parse_box_scores_from_ndjson(text: str) -> list[BoxScore]:
    """Parse historical box scores from newline-delimited JSON (NDJSON).

    Each non-empty line must contain a single game object. Field names may
    use snake_case, camelCase, or common historical export aliases.
    """
    scores: list[BoxScore] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue

        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"NDJSON line {line_number}: invalid JSON") from exc

        if not isinstance(record, dict):
            raise ValueError(f"NDJSON line {line_number}: must be an object")

        try:
            scores.append(parse_box_score(record))
        except ValueError as exc:
            message = str(exc)
            if message.startswith("NDJSON line"):
                raise
            raise ValueError(f"NDJSON line {line_number}: {message}") from exc

    return scores
