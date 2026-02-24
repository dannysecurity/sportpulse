from __future__ import annotations

import re

REQUIRED_FIELDS = ("home", "away", "home_score", "away_score")
OPTIONAL_FIELDS = ("played_on",)
CANONICAL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# Common aliases from historical exports, spreadsheets, and API dumps.
_FIELD_ALIASES: dict[str, str] = {
    "home": "home",
    "away": "away",
    "home_team": "home",
    "away_team": "away",
    "hometeam": "home",
    "awayteam": "away",
    "home team": "home",
    "away team": "away",
    "team_home": "home",
    "team_away": "away",
    "host": "home",
    "host_team": "home",
    "visitor": "away",
    "visitor_team": "away",
    "visiting": "away",
    "visiting_team": "away",
    "guest": "away",
    "guest_team": "away",
    "home_score": "home_score",
    "away_score": "away_score",
    "home_pts": "home_score",
    "away_pts": "away_score",
    "homepoints": "home_score",
    "awaypoints": "away_score",
    "home_points": "home_score",
    "away_points": "away_score",
    "home score": "home_score",
    "away score": "away_score",
    "pts_home": "home_score",
    "pts_away": "away_score",
    "homepts": "home_score",
    "awaypts": "away_score",
    "score_home": "home_score",
    "score_away": "away_score",
    "home_final": "home_score",
    "away_final": "away_score",
    "final_home": "home_score",
    "final_away": "away_score",
    "played_on": "played_on",
    "date": "played_on",
    "game_date": "played_on",
    "gamedate": "played_on",
    "game date": "played_on",
    "match_date": "played_on",
    "event_date": "played_on",
}

_CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")


def _normalize_key(key: str) -> str:
    """Lowercase and collapse separators for alias lookup."""
    snake = _CAMEL_RE.sub(r"\1_\2", key).replace("-", "_").lower()
    return snake.replace(" ", "_")


def canonical_field_name(key: str) -> str | None:
    """Map a raw field or column name to a canonical box score key."""
    normalized = _normalize_key(key)
    compact = normalized.replace("_", " ")
    return _FIELD_ALIASES.get(normalized) or _FIELD_ALIASES.get(compact)


def normalize_box_score_record(data: dict[str, object]) -> dict[str, object]:
    """Map historical export keys onto the canonical snake_case schema."""
    normalized: dict[str, object] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        canonical = canonical_field_name(key)
        if canonical is None:
            continue
        if canonical not in normalized or normalized[canonical] in (None, ""):
            normalized[canonical] = value
    return normalized


def normalize_csv_headers(headers: list[str]) -> dict[str, str]:
    """Return a mapping from original CSV headers to canonical field names."""
    mapping: dict[str, str] = {}
    for header in headers:
        canonical = canonical_field_name(header)
        if canonical is not None:
            mapping[header] = canonical
    return mapping
