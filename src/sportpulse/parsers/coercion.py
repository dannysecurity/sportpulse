from __future__ import annotations

import re
from datetime import date

_US_DATE_RE = re.compile(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$")


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


def _parse_us_style_date(stripped: str) -> date | None:
    """Parse MM/DD/YYYY or MM-DD-YYYY dates common in historical CSV exports."""
    match = _US_DATE_RE.match(stripped)
    if match is None:
        return None
    month, day, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"invalid played_on date: {stripped!r}") from exc


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
        except ValueError:
            us_date = _parse_us_style_date(stripped)
            if us_date is not None:
                return us_date
            raise ValueError(f"invalid played_on date: {value!r}") from None
    raise ValueError("played_on must be an ISO date string or null")
