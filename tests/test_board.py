from datetime import date
from pathlib import Path

from sportpulse.board import (
    annotate_board_game,
    build_board_highlights,
    build_board_report,
    build_multi_day_board_report,
    build_today_board_report,
    classify_confidence,
    filter_board_games,
    format_board_compact,
    format_board_csv,
    format_board_table,
    sort_board_games,
    spread_magnitude,
)
from sportpulse.cli import main
from sportpulse.matchups import build_matchups_report, load_matchups
from sportpulse.parsers import load_box_scores

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _sample_report():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    return build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )


def test_spread_magnitude_uses_absolute_value():
    game = {"home_spread": -4.5}
    assert spread_magnitude(game) == 4.5


def test_classify_confidence_tiers():
    assert classify_confidence({"home_spread": 1.0}) == "toss_up"
    assert classify_confidence({"home_spread": 4.0}) == "lean"
    assert classify_confidence({"home_spread": -7.5}) == "strong"


def test_annotate_board_game_adds_pick_and_confidence():
    game = {
        "home": "Celtics",
        "away": "Knicks",
        "home_spread": -4.5,
        "home_win_prob": 0.62,
        "away_win_prob": 0.38,
    }
    annotated = annotate_board_game(game)

    assert annotated["board_favorite"] == "Celtics"
    assert annotated["board_pick"] == "Celtics -4.5"
    assert annotated["board_confidence"] == "lean"
    assert annotated["board_spread_magnitude"] == 4.5


def test_build_board_report_sorts_by_spread():
    report = _sample_report()
    board = build_board_report(report, sort_by="spread")
    games = board["matchups"]

    magnitudes = [game["board_spread_magnitude"] for game in games]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_build_board_report_filters_by_min_spread():
    report = _sample_report()
    board = build_board_report(report, min_spread=5.0)

    assert board["board"]["games_shown"] <= board["board"]["games_total"]
    for game in board["matchups"]:
        assert game["board_spread_magnitude"] >= 5.0


def test_build_board_report_filters_by_confidence():
    report = _sample_report()
    board = build_board_report(report, confidence="lean")

    for game in board["matchups"]:
        assert game["board_confidence"] == "lean"


def test_sort_board_games_by_time():
    games = [
        {"away": "A", "home": "B", "start_time": "19:30"},
        {"away": "C", "home": "D", "start_time": "17:00"},
    ]
    sorted_games = sort_board_games(games, "time")

    assert sorted_games[0]["start_time"] == "17:00"


def test_filter_board_games_combines_filters():
    games = [
        {"board_confidence": "strong", "home_spread": -8.0},
        {"board_confidence": "lean", "home_spread": -4.0},
        {"board_confidence": "strong", "home_spread": -2.0},
    ]
    filtered = filter_board_games(games, min_spread=3.0, confidence="strong")

    assert len(filtered) == 1
    assert filtered[0]["home_spread"] == -8.0


def test_build_board_highlights_includes_counts():
    report = _sample_report()
    board = build_board_report(report)
    highlights = board["board"]["highlights"]

    assert highlights["strongest_favorite"] is not None
    assert highlights["closest_game"] is not None
    assert sum(highlights["confidence_counts"].values()) == len(board["matchups"])


def test_format_board_table_shows_confidence_and_pick():
    report = _sample_report()
    board = build_board_report(report)
    table = format_board_table(board)

    assert "Board 2026-01-16" in table
    assert "CONF" in table
    assert "PICK" in table
    assert "Highlights:" in table


def test_format_board_compact_one_line_per_game():
    report = _sample_report()
    board = build_board_report(report)
    compact = format_board_compact(board)

    assert compact.count("@") == len(board["matchups"])
    assert "|" in compact


def test_format_board_csv_header_and_rows():
    report = _sample_report()
    board = build_board_report(report)
    csv_text = format_board_csv(board)

    lines = csv_text.splitlines()
    assert lines[0].startswith("date,start_time,away,home")
    assert len(lines) == len(board["matchups"]) + 1


def test_cli_board_table(capsys):
    exit_code = main(
        [
            "board",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-16",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Board 2026-01-16" in output
    assert "CONF" in output


def test_cli_board_csv(capsys):
    exit_code = main(
        [
            "board",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-16",
            "--format",
            "csv",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "board_pick" in output
    assert "Knicks" in output


def test_cli_board_compact(capsys):
    exit_code = main(
        [
            "board",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-16",
            "--format",
            "compact",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "1." in output
    assert "@" in output


def test_cli_board_empty_after_filter_exit_code(capsys):
    exit_code = main(
        [
            "board",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-02-01",
            "--no-next",
            "--min-spread",
            "50",
        ]
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "No games on the board" in output


def test_load_matchups_parses_start_time(tmp_path: Path):
    path = tmp_path / "matchups.json"
    path.write_text(
        '[{"home":"Celtics","away":"Knicks","scheduled_on":"2026-01-16","start_time":"19:30"}]',
        encoding="utf-8",
    )
    matchups = load_matchups(path)

    assert matchups[0].start_time == "19:30"


def _multi_day_report():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    return build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
        days=2,
    )


def test_build_multi_day_board_report_annotates_all_slates():
    report = build_multi_day_board_report(_multi_day_report(), sort_by="time")

    assert len(report["slates"]) == 2
    assert report["board"]["games_shown"] == 3
    for slate in report["slates"]:
        for game in slate["matchups"]:
            assert "board_pick" in game
            assert "board_confidence" in game


def test_build_today_board_report_sets_title_label():
    report = build_today_board_report(_multi_day_report(), sort_by="time")

    assert report["title_label"] == "Today"
    assert report["board"]["games_shown"] == 3


def test_format_board_table_multi_day_shows_confidence_and_sections():
    report = build_today_board_report(_multi_day_report(), sort_by="time")
    table = format_board_table(report)

    assert "Today 2026-01-16 — 2026-01-17 (2 days)" in table
    assert "--- 2026-01-16 ---" in table
    assert "--- 2026-01-17 ---" in table
    assert "CONF" in table
    assert "Highlights:" in table
    assert "Window:" in table


def test_format_board_csv_multi_day_includes_all_games():
    report = build_today_board_report(_multi_day_report(), sort_by="time")
    csv_text = format_board_csv(report)

    lines = csv_text.splitlines()
    assert len(lines) == 4
    assert "2026-01-16" in csv_text
    assert "2026-01-17" in csv_text


def test_format_board_compact_multi_day():
    report = build_today_board_report(_multi_day_report(), sort_by="time")
    compact = format_board_compact(report)

    assert "--- 2026-01-16 ---" in compact
    assert "--- 2026-01-17 ---" in compact
    assert compact.count("@") == 3
