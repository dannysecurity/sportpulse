from __future__ import annotations

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.coercion import coerce_played_on, coerce_score
from sportpulse.parsers.schema import REQUIRED_FIELDS, normalize_box_score_record


def parse_box_score(data: dict[str, object]) -> BoxScore:
    """Build a BoxScore from a mapping with snake_case or aliased keys."""
    record = normalize_box_score_record(data)
    missing = [key for key in REQUIRED_FIELDS if key not in record]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"box score missing required field(s): {joined}")

    home = record["home"]
    away = record["away"]
    if not isinstance(home, str) or not isinstance(away, str):
        raise ValueError("home and away must be strings")
    home = home.strip()
    away = away.strip()
    if not home or not away:
        raise ValueError("home and away must be non-empty strings")

    home_score = coerce_score(record["home_score"], "home_score")
    away_score = coerce_score(record["away_score"], "away_score")

    played_on = None
    if "played_on" in record:
        played_on = coerce_played_on(record["played_on"])

    return BoxScore(
        home=home,
        away=away,
        home_score=home_score,
        away_score=away_score,
        played_on=played_on,
    )
