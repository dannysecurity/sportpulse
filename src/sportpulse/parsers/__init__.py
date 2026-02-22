"""Historical box score parsers for JSON, CSV, and NDJSON exports."""

from sportpulse.parsers.box_score import parse_box_score
from sportpulse.parsers.csv_parser import parse_box_scores_from_csv
from sportpulse.parsers.format_detect import detect_box_score_format
from sportpulse.parsers.import_audit import (
    BoxScoreImportAudit,
    DuplicateGame,
    audit_box_scores,
    import_box_scores_with_audit,
)
from sportpulse.parsers.json_parser import parse_box_scores_from_json
from sportpulse.parsers.loader import clear_box_score_cache, load_box_scores
from sportpulse.parsers.ndjson_parser import parse_box_scores_from_ndjson
from sportpulse.parsers.schema import (
    CANONICAL_FIELDS,
    REQUIRED_FIELDS,
    canonical_field_name,
    normalize_box_score_record,
    normalize_csv_headers,
)
from sportpulse.parsers.serialization import box_scores_to_json
from sportpulse.parsers.text_parser import parse_box_scores_text

__all__ = [
    "BoxScoreImportAudit",
    "CANONICAL_FIELDS",
    "DuplicateGame",
    "REQUIRED_FIELDS",
    "audit_box_scores",
    "box_scores_to_json",
    "canonical_field_name",
    "clear_box_score_cache",
    "detect_box_score_format",
    "import_box_scores_with_audit",
    "load_box_scores",
    "normalize_box_score_record",
    "normalize_csv_headers",
    "parse_box_score",
    "parse_box_scores_from_csv",
    "parse_box_scores_from_json",
    "parse_box_scores_from_ndjson",
    "parse_box_scores_text",
]
