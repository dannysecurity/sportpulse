from __future__ import annotations

from datetime import date


def coerce_score(value: object, field: str) -> int:
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


def coerce_played_on(value: object) -> date | None:
    """Normalize an optional game date from JSON or CSV."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return date.fromisoformat(stripped)
        except ValueError as exc:
            raise ValueError(f"invalid played_on date: {value!r}") from exc
    raise ValueError("played_on must be an ISO date string or null")
