from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.text_parser import parse_box_scores_text


@dataclass(frozen=True)
class DuplicateGame:
    """A box score that appears more than once in an import."""

    home: str
    away: str
    played_on: date | None
    count: int


@dataclass(frozen=True)
class BoxScoreImportAudit:
    """Summary of a historical box score import for validation and reporting."""

    format: str
    game_count: int
    teams: tuple[str, ...]
    first_played_on: date | None
    last_played_on: date | None
    duplicates: tuple[DuplicateGame, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the audit for CLI and API output."""
        payload: dict[str, object] = {
            "format": self.format,
            "game_count": self.game_count,
            "teams": list(self.teams),
            "duplicates": [
                {
                    "home": duplicate.home,
                    "away": duplicate.away,
                    "played_on": duplicate.played_on.isoformat()
                    if duplicate.played_on
                    else None,
                    "count": duplicate.count,
                }
                for duplicate in self.duplicates
            ],
        }
        if self.first_played_on is not None or self.last_played_on is not None:
            payload["date_range"] = {
                "first": self.first_played_on.isoformat()
                if self.first_played_on
                else None,
                "last": self.last_played_on.isoformat() if self.last_played_on else None,
            }
        return payload


def _game_key(score: BoxScore) -> tuple[str, str, date | None]:
    return (score.home, score.away, score.played_on)


def audit_box_scores(scores: list[BoxScore], fmt: str) -> BoxScoreImportAudit:
    """Build an import audit from already-parsed box scores."""
    teams = sorted({score.home for score in scores} | {score.away for score in scores})
    dated = [score.played_on for score in scores if score.played_on is not None]

    counts: dict[tuple[str, str, date | None], int] = {}
    for score in scores:
        key = _game_key(score)
        counts[key] = counts.get(key, 0) + 1

    duplicates = tuple(
        DuplicateGame(home=key[0], away=key[1], played_on=key[2], count=count)
        for key, count in sorted(counts.items())
        if count > 1
    )

    return BoxScoreImportAudit(
        format=fmt,
        game_count=len(scores),
        teams=tuple(teams),
        first_played_on=min(dated) if dated else None,
        last_played_on=max(dated) if dated else None,
        duplicates=duplicates,
    )


def import_box_scores_with_audit(
    path: Path | str,
    fmt: str | None = None,
) -> tuple[list[BoxScore], BoxScoreImportAudit]:
    """Load a historical box score file and return parsed games plus an audit."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"box score file not found: {file_path}")

    text = file_path.read_text(encoding="utf-8")
    scores, resolved = parse_box_scores_text(
        text,
        fmt=fmt,
        suffix=file_path.suffix.lstrip("."),
    )
    return scores, audit_box_scores(scores, resolved)
