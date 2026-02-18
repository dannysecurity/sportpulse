from __future__ import annotations

from sportpulse.boxscore import BoxScore


def box_scores_to_json(scores: list[BoxScore]) -> list[dict[str, object]]:
    """Serialize parsed box scores for CLI/API output."""
    return [score.summary() for score in scores]
