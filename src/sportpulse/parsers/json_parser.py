from __future__ import annotations

import json

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.box_score import parse_box_score


def parse_box_scores_from_json(text: str) -> list[BoxScore]:
    """Parse historical box scores from JSON text.

    Accepts a single game object, a list of games, or a schedule-style
    wrapper with a top-level ``games`` array (matching ``Schedule.to_json``).
    Field names may use snake_case, camelCase, or common historical aliases.
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
