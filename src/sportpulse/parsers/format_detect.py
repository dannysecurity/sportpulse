from __future__ import annotations

from sportpulse.parsers.schema import REQUIRED_FIELDS, normalize_csv_headers


def detect_box_score_format(text: str, suffix: str | None = None) -> str:
    """Infer the historical box score format from a file suffix or payload.

    Supports JSON (object, array, or schedule wrapper), CSV with a header row,
    and NDJSON (one game object per line). When the suffix is absent or
    ambiguous, the payload content is inspected.
    """
    ext = (suffix or "").lstrip(".").lower()
    if ext in ("ndjson", "jsonl"):
        return "ndjson"
    if ext == "csv":
        return "csv"
    if ext in ("json", "js"):
        return "json"

    stripped = text.lstrip("\ufeff").lstrip()
    if not stripped:
        raise ValueError("empty box score input")

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) > 1 and all(line.startswith("{") for line in lines):
        return "ndjson"
    if stripped[0] in "{[":
        return "json"

    first_line = lines[0] if lines else stripped.splitlines()[0]
    if "," in first_line:
        headers = [part.strip() for part in first_line.split(",")]
        canonical = set(normalize_csv_headers(headers).values())
        if all(field in canonical for field in REQUIRED_FIELDS):
            return "csv"

    raise ValueError(
        "unable to detect box score format (expected json, csv, or ndjson)"
    )
