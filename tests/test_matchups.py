from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.cli import main
from sportpulse.matchups import (
    build_matchups_report,
    build_range_summary,
    build_slate_summary,
    clear_matchups_cache,
    format_matchups_compact,
    format_matchups_csv,
    format_matchups_report,
    format_matchups_summary,
    format_matchups_table,
    last_slate_date,
    load_matchups,
    matchups_for_date,
    matchups_in_range,
    matchups_involving_team,
    next_slate_date,
    probability_to_american_odds,
    project_matchup,
    rating_gap_to_spread,
    ratings_from_history,
    resolve_slate_date,
)
from sportpulse.parsers import load_box_scores
from sportpulse.projections import build_scoring_profiles

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_load_matchups_from_example():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")

    assert len(matchups) == 3
    assert matchups[0].home == "Celtics"
    assert matchups[0].scheduled_on == date(2026, 1, 16)


def test_load_matchups_reuses_cache_until_file_changes(tmp_path: Path):
    clear_matchups_cache()
    path = tmp_path / "matchups.json"
    path.write_text(
        '[{"home":"Celtics","away":"Knicks","scheduled_on":"2026-01-16"}]',
        encoding="utf-8",
    )

    first = load_matchups(path)
    second = load_matchups(path)
    assert first is second

    path.write_text(
        '[{"home":"Lakers","away":"Heat","scheduled_on":"2026-01-17","venue":"Staples"}]',
        encoding="utf-8",
    )
    reloaded = load_matchups(path)
    assert reloaded is not first
    assert reloaded[0].home == "Lakers"


def test_matchups_for_date_filters_slate():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    slate = matchups_for_date(matchups, date(2026, 1, 16))

    assert len(slate) == 2
    assert {game.away for game in slate} == {"Knicks", "Heat"}


def test_ratings_from_history_uses_sample_season():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    ratings = ratings_from_history(scores)

    assert ratings["Lakers"] > 1500.0
    assert "Celtics" in ratings


def test_ratings_from_history_replays_games_chronologically():
    games = [
        BoxScore("Lakers", "Celtics", 112, 108, date(2026, 1, 10)),
        BoxScore("Warriors", "Lakers", 99, 102, date(2026, 1, 12)),
        BoxScore("Lakers", "Knicks", 105, 101, date(2026, 1, 14)),
    ]
    chronological = ratings_from_history(games)
    shuffled = ratings_from_history(list(reversed(games)))

    assert shuffled == chronological


def test_project_matchup_returns_probabilities():
    matchup = load_matchups(EXAMPLES_DIR / "matchups.json")[0]
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    ratings = ratings_from_history(scores)
    profiles = build_scoring_profiles(scores)

    projection = project_matchup(matchup, ratings, scoring_profiles=profiles)

    assert projection["home"] == "Celtics"
    assert projection["away_win_prob"] == round(1.0 - projection["home_win_prob"], 3)
    assert 0.0 < projection["home_win_prob"] < 1.0
    assert isinstance(projection["home_spread"], float)
    assert isinstance(projection["home_moneyline"], int)
    assert isinstance(projection["away_moneyline"], int)
    assert "projected_total" in projection
    assert projection["projected_total"] > 0


def test_probability_to_american_odds():
    assert probability_to_american_odds(0.667) == -200
    assert probability_to_american_odds(0.333) == 200
    assert probability_to_american_odds(0.5) == -100


def test_rating_gap_to_spread():
    assert rating_gap_to_spread(100.0) == -4.0
    assert rating_gap_to_spread(-50.0) == 2.0
    assert rating_gap_to_spread(100.0, points_per_100_elo=5.0) == -5.0


def test_build_slate_summary_counts_favorites_and_totals():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    summary = report["summary"]

    assert summary["games"] == 2
    assert summary["home_favorites"] + summary["away_favorites"] + summary["pick_em_games"] == 2
    assert summary["has_scoring_projections"] is True
    assert summary["avg_projected_total"] is not None
    assert summary["biggest_spread_game"] is not None
    assert summary["closest_game"] is not None


def test_build_slate_summary_empty_slate():
    summary = build_slate_summary([])

    assert summary["games"] == 0
    assert summary["avg_projected_total"] is None
    assert summary["has_scoring_projections"] is False


def test_format_matchups_table_includes_slate_summary():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    table = format_matchups_table(report)

    assert "Slate:" in table
    assert "home fav" in table
    assert "avg O/U" in table


def test_project_matchup_respects_spread_scale():
    matchup = load_matchups(EXAMPLES_DIR / "matchups.json")[0]
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    ratings = ratings_from_history(scores)

    default_spread = project_matchup(matchup, ratings)["home_spread"]
    wider_spread = project_matchup(
        matchup,
        ratings,
        points_per_100_elo=8.0,
    )["home_spread"]

    assert isinstance(default_spread, float)
    assert isinstance(wider_spread, float)
    assert abs(wider_spread) > abs(default_spread)


def test_cli_matchups_empty_slate_exit_code(capsys):
    exit_code = main(
        [
            "matchups",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--date",
            "2026-02-01",
            "--format",
            "table",
        ]
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "0 game(s)" in output


def test_cli_today_auto_advances_to_next_slate(capsys):
    exit_code = main(
        [
            "today",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-15",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "requested 2026-01-15, next slate" in output
    assert "Knicks @ Celtics" in output


def test_format_matchups_table(capsys):
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    table = format_matchups_table(report)

    assert "2026-01-16" in table
    assert "Knicks @ Celtics" in table
    assert "SPREAD" in table
    assert "ML(H)" in table
    assert "O/U" in table
    assert "19:30" in table
    assert "TIME" in table


def test_format_matchups_compact_one_line_per_game():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    compact = format_matchups_compact(report)

    assert "1. Knicks @ Celtics" in compact
    assert "2. Heat @ Warriors" in compact
    assert "|" in compact
    assert "O/U" in compact
    assert "Slate:" in compact


def test_format_matchups_csv_headers_and_rows():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    csv_output = format_matchups_csv(report)
    lines = csv_output.splitlines()

    assert lines[0].startswith("date,start_time,away,home,pick,")
    assert len(lines) == 1 + len(report["matchups"])
    assert "Knicks" in csv_output
    assert "Celtics" in csv_output


def test_format_matchups_report_dispatches_formats():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    assert "SPREAD" in format_matchups_report(report, "table")
    assert "|" in format_matchups_report(report, "compact")
    assert format_matchups_report(report, "csv").startswith("date,")
    assert format_matchups_report(report, "summary").startswith("2026-01-16")


def test_format_matchups_summary_one_line():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    summary = format_matchups_summary(report)
    lines = summary.splitlines()

    assert len(lines) == 2
    assert lines[0] == "2026-01-16 — 2 game(s)"
    assert lines[1].startswith("Slate:")
    assert "home fav" in lines[1]
    assert "avg O/U" in lines[1]
    assert "biggest spread:" in lines[1]
    assert "closest:" in lines[1]


def test_cli_today_summary(capsys):
    exit_code = main(
        [
            "today",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-16",
            "--format",
            "summary",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    lines = output.strip().splitlines()
    assert len(lines) == 2
    assert "2026-01-16 — 2 game(s)" in lines[0]
    assert lines[1].startswith("Slate:")


def test_build_matchups_report_for_date():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
    )

    assert report["date"] == "2026-01-16"
    assert report["requested_date"] == "2026-01-16"
    assert report["advanced_to_next_slate"] is False
    assert len(report["matchups"]) == 2
    assert all("home_win_prob" in game for game in report["matchups"])
    assert all("home_moneyline" in game for game in report["matchups"])
    assert all("projected_total" in game for game in report["matchups"])


def test_next_slate_date_skips_empty_days():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")

    assert next_slate_date(matchups, date(2026, 1, 15)) == date(2026, 1, 16)
    assert next_slate_date(matchups, date(2026, 1, 16)) == date(2026, 1, 16)
    assert next_slate_date(matchups, date(2026, 1, 18)) is None


def test_last_slate_date_returns_latest():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")

    assert last_slate_date(matchups) == date(2026, 1, 17)


def test_resolve_slate_date_advances_when_empty():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")

    unchanged = resolve_slate_date(matchups, date(2026, 1, 16))
    assert unchanged == (date(2026, 1, 16), False, False)

    advanced = resolve_slate_date(matchups, date(2026, 1, 15), advance_if_empty=True)
    assert advanced == (date(2026, 1, 16), True, False)


def test_resolve_slate_date_falls_back_to_last_slate():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")

    resolved = resolve_slate_date(matchups, date(2026, 2, 1), advance_if_empty=True)

    assert resolved == (date(2026, 1, 17), False, True)


def test_build_matchups_report_advances_with_next_flag():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 15),
        advance_if_empty=True,
    )

    assert report["requested_date"] == "2026-01-15"
    assert report["date"] == "2026-01-16"
    assert report["advanced_to_next_slate"] is True
    assert report["advanced_to_last_slate"] is False
    assert len(report["matchups"]) == 2


def test_build_matchups_report_falls_back_to_last_slate():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 2, 1),
        advance_if_empty=True,
    )

    assert report["requested_date"] == "2026-02-01"
    assert report["date"] == "2026-01-17"
    assert report["advanced_to_next_slate"] is False
    assert report["advanced_to_last_slate"] is True
    assert len(report["matchups"]) == 1
    assert report["matchups"][0]["home"] == "Lakers"


def test_matchups_involving_team_filters_slate():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    lakers_day = matchups_involving_team(matchups, "Lakers", on_date=date(2026, 1, 17))

    assert len(lakers_day) == 1
    assert lakers_day[0].away == "Nuggets"


def test_build_matchups_report_team_filter():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        team="Celtics",
    )

    assert report["team_filter"] == "Celtics"
    assert len(report["matchups"]) == 1
    assert report["matchups"][0]["home"] == "Celtics"


def test_format_matchups_table_shows_next_slate_banner():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 15),
        advance_if_empty=True,
    )

    table = format_matchups_table(report)

    assert "requested 2026-01-15, next slate" in table
    assert "Knicks @ Celtics" in table


def test_format_matchups_table_shows_last_slate_banner():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 2, 1),
        advance_if_empty=True,
    )

    table = format_matchups_table(report)

    assert "requested 2026-02-01, last slate" in table
    assert "Nuggets @ Lakers" in table


def test_cli_today_falls_back_to_last_slate_when_past_all_games(capsys):
    exit_code = main(
        [
            "today",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-07-08",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "requested 2026-07-08, last slate" in output
    assert "Nuggets @ Lakers" in output


def test_format_matchups_table_empty_slate_message():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    report = build_matchups_report(matchups, on_date=date(2026, 2, 1))

    table = format_matchups_table(report)

    assert "0 game(s)" in table
    assert "No games scheduled for this slate." in table


def test_cli_today_uses_config_defaults(capsys):
    exit_code = main(
        [
            "today",
            "--date",
            "2026-01-16",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Knicks @ Celtics" in output
    assert "O/U" in output


def test_cli_today_defaults_to_table(capsys):
    exit_code = main(
        [
            "today",
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
    assert "SPREAD" in output
    assert '"home_win_prob"' not in output


def test_cli_matchups_next_flag(capsys):
    exit_code = main(
        [
            "matchups",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--date",
            "2026-01-15",
            "--next",
            "--format",
            "table",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "requested 2026-01-15, next slate" in output


def test_cli_matchups_table(capsys):
    exit_code = main(
        [
            "matchups",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-16",
            "--format",
            "table",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Knicks @ Celtics" in output
    assert "SPREAD" in output


def test_cli_matchups_json(capsys):
    exit_code = main(
        [
            "matchups",
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
    assert '"date": "2026-01-16"' in output
    assert '"home_win_prob"' in output
    assert '"home_moneyline"' in output


def test_cli_today_compact(capsys):
    exit_code = main(
        [
            "today",
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
    assert "Knicks @ Celtics" in output
    assert "|" in output
    assert "SPREAD" not in output


def test_cli_matchups_csv(capsys):
    exit_code = main(
        [
            "matchups",
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
    assert output.startswith("date,start_time,away,home,pick,")
    assert "Knicks" in output


def test_matchups_in_range_groups_consecutive_days():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")

    grouped = matchups_in_range(matchups, date(2026, 1, 16), days=2)

    assert len(grouped) == 2
    assert grouped[0][0] == date(2026, 1, 16)
    assert len(grouped[0][1]) == 2
    assert grouped[1][0] == date(2026, 1, 17)
    assert len(grouped[1][1]) == 1


def test_build_matchups_report_multi_day_window():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
        days=2,
    )

    assert report["start_date"] == "2026-01-16"
    assert report["end_date"] == "2026-01-17"
    assert report["days"] == 2
    assert len(report["slates"]) == 2
    assert report["summary"]["games"] == 3
    assert report["summary"]["days_with_games"] == 2
    assert all("projected_total" in game for slate in report["slates"] for game in slate["matchups"])


def test_build_range_summary_aggregates_slates():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
        days=2,
    )

    summary = build_range_summary(report["slates"])

    assert summary["games"] == 3
    assert summary["days"] == 2
    assert summary["days_with_games"] == 2
    assert summary["has_scoring_projections"] is True


def test_format_matchups_table_multi_day():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
        days=2,
    )

    table = format_matchups_table(report)

    assert "2026-01-16 — 2026-01-17 (2 days)" in table
    assert "Knicks @ Celtics" in table
    assert "Nuggets @ Lakers" in table
    assert "Window:" in table


def test_format_matchups_compact_multi_day():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
        days=2,
    )

    compact = format_matchups_compact(report)

    assert "--- 2026-01-16 ---" in compact
    assert "--- 2026-01-17 ---" in compact
    assert "1. Knicks @ Celtics" in compact
    assert "3. Nuggets @ Lakers" in compact


def test_format_matchups_csv_multi_day():
    matchups = load_matchups(EXAMPLES_DIR / "matchups.json")
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    report = build_matchups_report(
        matchups,
        on_date=date(2026, 1, 16),
        history=scores,
        days=2,
    )

    csv_output = format_matchups_csv(report)
    lines = csv_output.splitlines()

    assert len(lines) == 1 + report["summary"]["games"]
    assert "2026-01-16" in csv_output
    assert "2026-01-17" in csv_output


def test_cli_today_multi_day_window(capsys):
    exit_code = main(
        [
            "today",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--history",
            str(EXAMPLES_DIR / "season.json"),
            "--date",
            "2026-01-16",
            "--days",
            "2",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "2026-01-16 — 2026-01-17 (2 days)" in output
    assert "Knicks @ Celtics" in output
    assert "Nuggets @ Lakers" in output


def test_cli_matchups_days_must_be_positive(capsys):
    exit_code = main(
        [
            "matchups",
            "--file",
            str(EXAMPLES_DIR / "matchups.json"),
            "--days",
            "0",
        ]
    )

    assert exit_code == 2
    assert "--days must be at least 1" in capsys.readouterr().err
