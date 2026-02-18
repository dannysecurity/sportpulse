from __future__ import annotations

from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.csv_parser import parse_box_scores_from_csv
from sportpulse.parsers.json_parser import parse_box_scores_from_json

_box_score_cache: dict[tuple[str, str | None], tuple[int, int, list[BoxScore]]] = {}


def clear_box_score_cache() -> None:
    """Clear the in-process box score file cache."""
    _box_score_cache.clear()


def _read_box_scores(file_path: Path, fmt: str | None) -> list[BoxScore]:
    resolved = (fmt or file_path.suffix.lstrip(".")).lower()
    text = file_path.read_text(encoding="utf-8")

    if resolved in ("json", "js"):
        return parse_box_scores_from_json(text)
    if resolved == "csv":
        return parse_box_scores_from_csv(text)

    raise ValueError(f"unsupported box score format: {resolved!r} (use json or csv)")


def load_box_scores(path: Path | str, fmt: str | None = None) -> list[BoxScore]:
    """Load historical box scores from a JSON or CSV file.

    Parsed results are cached in-process keyed by resolved path, format, and
    file modification time so repeated loads skip disk I/O and parsing.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"box score file not found: {file_path}")

    resolved_path = file_path.resolve()
    stat = resolved_path.stat()
    cache_key = (str(resolved_path), fmt)
    cached = _box_score_cache.get(cache_key)
    if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]

    scores = _read_box_scores(resolved_path, fmt)
    _box_score_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, scores)
    return scores
