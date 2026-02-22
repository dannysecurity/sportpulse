from __future__ import annotations

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.csv_parser import parse_box_scores_from_csv
from sportpulse.parsers.format_detect import detect_box_score_format
from sportpulse.parsers.json_parser import parse_box_scores_from_json
from sportpulse.parsers.ndjson_parser import parse_box_scores_from_ndjson

_SUPPORTED_FORMATS = ("json", "csv", "ndjson")


def parse_box_scores_text(
    text: str,
    fmt: str | None = None,
    *,
    suffix: str | None = None,
) -> tuple[list[BoxScore], str]:
    """Parse historical box scores from in-memory text.

    Returns the parsed scores and the resolved format name.
    """
    resolved = (fmt or detect_box_score_format(text, suffix=suffix)).lower()
    if resolved not in _SUPPORTED_FORMATS:
        joined = ", ".join(_SUPPORTED_FORMATS)
        raise ValueError(f"unsupported box score format: {resolved!r} (use {joined})")

    if resolved == "json":
        return parse_box_scores_from_json(text), resolved
    if resolved == "csv":
        return parse_box_scores_from_csv(text), resolved
    return parse_box_scores_from_ndjson(text), resolved
