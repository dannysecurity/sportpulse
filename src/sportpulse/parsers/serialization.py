from __future__ import annotations

import csv
from io import StringIO

from sportpulse.boxscore import BoxScore
from sportpulse.parsers.schema import CANONICAL_FIELDS


def box_scores_to_json(scores: list[BoxScore]) -> list[dict[str, object]]:
    """Serialize parsed box scores for CLI/API output."""
    return [score.summary() for score in scores]


def box_scores_to_csv(scores: list[BoxScore]) -> str:
    """Serialize parsed box scores as canonical CSV for spreadsheet exports.

    Output uses the canonical column names so files can be re-imported with
    ``load_box_scores`` or normalized from historical alias headers.
    """
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CANONICAL_FIELDS)
    for score in scores:
        writer.writerow(
            [
                score.home,
                score.away,
                score.home_score,
                score.away_score,
                score.played_on.isoformat() if score.played_on else "",
            ]
        )
    return buffer.getvalue()
