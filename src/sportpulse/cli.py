from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from sportpulse.board import (
    FORMAT_OPTIONS as BOARD_FORMAT_OPTIONS,
    SORT_OPTIONS as BOARD_SORT_OPTIONS,
    BoardFormat,
    build_board_report,
    format_board_report,
)
from sportpulse.boxscore import BoxScore
from sportpulse.config import resolve_matchups_paths
from sportpulse.elo import EloCalculator
from sportpulse.matchups import FORMAT_OPTIONS as MATCHUPS_FORMAT_OPTIONS, format_matchups_report
from sportpulse.parsers import (
    box_scores_to_csv,
    box_scores_to_json,
    import_box_scores_with_audit,
    load_box_scores,
)
from sportpulse.ratings import (
    build_batch_rating_update_report,
    build_rating_update_report,
    build_ratings_leaderboard,
    format_rating_update_table,
    format_ratings_table,
)
from sportpulse.schedule_cache import (
    load_matchups_report,
    load_season_report,
    load_standings_report,
)
from sportpulse.standings import format_standings_table


def _add_matchups_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--file",
        help="Path to scheduled matchups JSON (defaults to sportpulse.json or examples/)",
    )
    parser.add_argument(
        "--history",
        help="Optional JSON or CSV season file for ELO ratings and scoring pace",
    )
    parser.add_argument(
        "--config",
        help="Path to sportpulse.json config (auto-discovered from cwd when omitted)",
    )
    parser.add_argument(
        "--date",
        help="Calendar day to show (ISO, defaults to today)",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        default=None,
        help="When the requested day has no games, show the next scheduled slate",
    )
    parser.add_argument(
        "--no-next",
        action="store_false",
        dest="next",
        help="Only show games on the requested day",
    )
    parser.add_argument(
        "--team",
        help="Only show matchups involving this team",
    )
    parser.add_argument("--k-factor", type=float, default=None)
    parser.add_argument(
        "--home-advantage",
        type=float,
        default=None,
        help="ELO points added for the home team in projections",
    )
    parser.add_argument(
        "--points-per-100-elo",
        type=float,
        default=None,
        help="Point spread per 100 ELO rating gap (default 4.0)",
    )
    parser.add_argument(
        "--home-court-points",
        type=float,
        default=None,
        help="Scoring boost applied to the home team in O/U projections",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of consecutive calendar days to show (default 1)",
    )
    parser.add_argument(
        "--format",
        choices=MATCHUPS_FORMAT_OPTIONS,
        default="json",
        help="Output format (json, table, compact, csv, or summary)",
    )


def _add_board_options(parser: argparse.ArgumentParser) -> None:
    _add_matchups_options(parser)
    parser.set_defaults(format="table")
    parser.add_argument(
        "--sort",
        choices=BOARD_SORT_OPTIONS,
        default="spread",
        help="Sort order for the game-day board (default: spread magnitude)",
    )
    parser.add_argument(
        "--min-spread",
        type=float,
        default=None,
        help="Only show games with at least this spread magnitude",
    )
    parser.add_argument(
        "--confidence",
        choices=("toss_up", "lean", "strong"),
        default=None,
        help="Only show games in this confidence tier",
    )
    for action in parser._actions:
        if action.dest == "format":
            action.choices = BOARD_FORMAT_OPTIONS
            action.help = "Output format (table, compact, csv, or json)"
            break


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sportpulse",
        description="Sports stats toolkit — box scores, schedules, and ELO trends.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    box = sub.add_parser("boxscore", help="Summarize a game box score")
    box.add_argument("--home", required=True)
    box.add_argument("--away", required=True)
    box.add_argument("--home-score", type=int, required=True)
    box.add_argument("--away-score", type=int, required=True)

    elo = sub.add_parser("elo", help="Compute ELO updates for a result")
    elo.add_argument("--team-a", required=True)
    elo.add_argument("--rating-a", type=float, required=True)
    elo.add_argument("--team-b", required=True)
    elo.add_argument("--rating-b", type=float, required=True)
    elo.add_argument("--score-a", type=int, required=True)
    elo.add_argument("--score-b", type=int, required=True)
    elo.add_argument("--k-factor", type=float, default=20.0)

    serve = sub.add_parser("serve", help="Start the JSON API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    import_scores = sub.add_parser(
        "import-boxscores",
        help="Parse historical box scores from a JSON, CSV, or NDJSON file",
    )
    import_scores.add_argument("--file", required=True, help="Path to the input file")
    import_scores.add_argument(
        "--format",
        choices=("json", "csv", "ndjson"),
        help="Input format (defaults to the file extension or auto-detection)",
    )
    import_scores.add_argument(
        "--audit",
        action="store_true",
        help="Include an import audit (teams, date range, duplicate games)",
    )
    import_scores.add_argument(
        "--output",
        choices=("json", "csv"),
        default="json",
        help="Output format (json or canonical CSV for spreadsheet export)",
    )

    season = sub.add_parser(
        "season-report",
        help="Compute team record and ELO trend from a season file",
    )
    season.add_argument("--team", required=True, help="Team to summarize")
    season.add_argument("--file", required=True, help="Path to JSON or CSV season data")
    season.add_argument(
        "--format",
        choices=("json", "csv"),
        help="Input format (defaults to the file extension)",
    )
    season.add_argument(
        "--start-date",
        help="Inclusive start date (ISO) for a filtered record slice",
    )
    season.add_argument(
        "--end-date",
        help="Inclusive end date (ISO) for a filtered record slice",
    )
    season.add_argument("--k-factor", type=float, default=20.0)

    ratings = sub.add_parser(
        "ratings",
        help="Show league ELO leaderboard from a season file",
    )
    ratings.add_argument("--file", required=True, help="Path to JSON or CSV season data")
    ratings.add_argument(
        "--format",
        choices=("json", "csv"),
        help="Input format (defaults to the file extension)",
    )
    ratings.add_argument("--k-factor", type=float, default=20.0)
    ratings.add_argument(
        "--home-advantage",
        type=float,
        default=0.0,
        help="ELO points credited to the home team during replay",
    )
    ratings.add_argument(
        "--output",
        choices=("json", "table"),
        default="json",
        help="Output format (json or human-readable table)",
    )

    update_ratings = sub.add_parser(
        "update-ratings",
        help="Apply a new game result to ELO ratings bootstrapped from history",
    )
    update_ratings.add_argument(
        "--history",
        help="Optional JSON or CSV season file to bootstrap ratings (defaults to 1500)",
    )
    update_ratings.add_argument(
        "--games-file",
        help="JSON or CSV file with one or more new results to apply in batch",
    )
    update_ratings.add_argument("--home", help="Home team name (single-game mode)")
    update_ratings.add_argument("--away", help="Away team name (single-game mode)")
    update_ratings.add_argument("--home-score", type=int, help="Home team score")
    update_ratings.add_argument("--away-score", type=int, help="Away team score")
    update_ratings.add_argument(
        "--played-on",
        help="Game date (ISO) recorded in rating history",
    )
    update_ratings.add_argument(
        "--format",
        choices=("json", "csv"),
        help="Input format for --history (defaults to the file extension)",
    )
    update_ratings.add_argument("--k-factor", type=float, default=20.0)
    update_ratings.add_argument(
        "--home-advantage",
        type=float,
        default=0.0,
        help="ELO points credited to the home team during replay and update",
    )
    update_ratings.add_argument(
        "--leaderboard",
        action="store_true",
        help="Include the full ranked leaderboard after the update",
    )
    update_ratings.add_argument(
        "--output",
        choices=("json", "table"),
        default="json",
        help="Output format (json or human-readable table)",
    )

    league = sub.add_parser(
        "standings",
        help="Show league win/loss standings from a season file",
    )
    league.add_argument("--file", required=True, help="Path to JSON or CSV season data")
    league.add_argument(
        "--format",
        choices=("json", "csv"),
        help="Input format (defaults to the file extension)",
    )
    league.add_argument(
        "--start-date",
        help="Inclusive start date (ISO) for a filtered standings slice",
    )
    league.add_argument(
        "--end-date",
        help="Inclusive end date (ISO) for a filtered standings slice",
    )
    league.add_argument(
        "--tie-breaker",
        choices=("win_pct", "point_diff", "team_name"),
        default="win_pct",
        help="Primary sort key when ranking teams",
    )
    league.add_argument(
        "--output",
        choices=("json", "table"),
        default="json",
        help="Output format (json or human-readable table)",
    )

    matchups = sub.add_parser(
        "matchups",
        help="Show a day's slate with odds-lite ELO win probabilities",
    )
    _add_matchups_options(matchups)

    today = sub.add_parser(
        "today",
        help="Show today's slate with odds-lite projections (table by default)",
    )
    _add_matchups_options(today)
    today.set_defaults(format="table", next=True)
    today.add_argument(
        "--sort",
        choices=BOARD_SORT_OPTIONS,
        default="time",
        help="Sort order for today's slate (default: start time)",
    )
    today.add_argument(
        "--min-spread",
        type=float,
        default=None,
        help="Only show games with at least this spread magnitude",
    )
    today.add_argument(
        "--confidence",
        choices=("toss_up", "lean", "strong"),
        default=None,
        help="Only show games in this confidence tier",
    )

    board = sub.add_parser(
        "board",
        help="Game-day odds-lite board with confidence tiers and sortable output",
    )
    _add_board_options(board)
    board.set_defaults(next=True)

    return parser


def cmd_boxscore(args: argparse.Namespace) -> int:
    score = BoxScore(
        home=args.home,
        away=args.away,
        home_score=args.home_score,
        away_score=args.away_score,
    )
    print(json.dumps(score.summary(), indent=2))
    return 0


def cmd_elo(args: argparse.Namespace) -> int:
    calc = EloCalculator(k_factor=args.k_factor)
    new_a, new_b = calc.update(
        args.rating_a,
        args.rating_b,
        score_a=args.score_a,
        score_b=args.score_b,
    )
    payload = {
        args.team_a: {"before": args.rating_a, "after": new_a, "delta": round(new_a - args.rating_a, 1)},
        args.team_b: {"before": args.rating_b, "after": new_b, "delta": round(new_b - args.rating_b, 1)},
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from sportpulse.api import run_server

    run_server(host=args.host, port=args.port)
    return 0


def cmd_import_boxscores(args: argparse.Namespace) -> int:
    if args.audit:
        scores, audit = import_box_scores_with_audit(args.file, fmt=args.format)
    else:
        scores = load_box_scores(args.file, fmt=args.format)

    if args.output == "csv":
        print(box_scores_to_csv(scores), end="")
        if args.audit:
            print(json.dumps(audit.to_dict(), indent=2), file=sys.stderr)
        return 0

    if args.audit:
        payload = {
            "games": box_scores_to_json(scores),
            "audit": audit.to_dict(),
        }
    else:
        payload = box_scores_to_json(scores)
    print(json.dumps(payload, indent=2))
    return 0


def _load_matchups_report_from_args(args: argparse.Namespace) -> tuple[dict[str, object], int | None]:
    """Resolve config and build a matchups report; return (report, error_code)."""
    on_date = date.fromisoformat(args.date) if args.date else date.today()
    try:
        paths = resolve_matchups_paths(
            matchups_file=args.file,
            history_file=args.history,
            config_file=args.config,
        )
    except FileNotFoundError as exc:
        print(f"matchups: {exc}", file=sys.stderr)
        return {}, 2

    if paths.history_file is None:
        print(
            "matchups: no history file configured; O/U totals omitted "
            "(pass --history or set history_file in sportpulse.json)",
            file=sys.stderr,
        )
    home_advantage = args.home_advantage if args.home_advantage is not None else paths.home_advantage
    k_factor = args.k_factor if args.k_factor is not None else paths.k_factor
    points_per_100_elo = (
        args.points_per_100_elo
        if args.points_per_100_elo is not None
        else paths.points_per_100_elo
    )
    home_court_points = (
        args.home_court_points
        if args.home_court_points is not None
        else paths.home_court_points
    )
    if args.days < 1:
        print("matchups: --days must be at least 1", file=sys.stderr)
        return {}, 2

    report = load_matchups_report(
        paths.matchups_file,
        on_date=on_date,
        history_file=paths.history_file,
        k_factor=k_factor,
        home_advantage=home_advantage,
        points_per_100_elo=points_per_100_elo,
        home_court_points=home_court_points,
        advance_if_empty=args.next if args.next is not None else False,
        team=args.team,
        days=args.days,
    )
    return report, None


def cmd_matchups(args: argparse.Namespace) -> int:
    report, error_code = _load_matchups_report_from_args(args)
    if error_code is not None:
        return error_code
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_matchups_report(report, args.format))

    summary = report.get("summary")
    if isinstance(summary, dict) and summary.get("games", 0) == 0:
        return 1
    return 0


def _today_board_format(fmt: str) -> BoardFormat | None:
    if fmt in BOARD_FORMAT_OPTIONS:
        return fmt  # type: ignore[return-value]
    return None


def cmd_today(args: argparse.Namespace) -> int:
    """Show today's slate with sortable odds-lite picks and confidence tiers."""
    report, error_code = _load_matchups_report_from_args(args)
    if error_code is not None:
        return error_code

    board_fmt = _today_board_format(args.format)
    use_board = board_fmt is not None and "slates" not in report

    if use_board:
        board_report = build_board_report(
            report,
            sort_by=args.sort,
            min_spread=args.min_spread,
            confidence=args.confidence,
        )
        board_report["title_label"] = "Today"
        if args.format == "json":
            print(json.dumps(board_report, indent=2))
        else:
            print(format_board_report(board_report, board_fmt))
        games_shown = board_report.get("board", {}).get("games_shown")
        if games_shown == 0:
            return 1
        return 0

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_matchups_report(report, args.format))

    summary = report.get("summary")
    if isinstance(summary, dict) and summary.get("games", 0) == 0:
        return 1
    return 0


def cmd_board(args: argparse.Namespace) -> int:
    report, error_code = _load_matchups_report_from_args(args)
    if error_code is not None:
        return error_code

    board_report = build_board_report(
        report,
        sort_by=args.sort,
        min_spread=args.min_spread,
        confidence=args.confidence,
    )
    if args.format == "json":
        print(json.dumps(board_report, indent=2))
    else:
        print(format_board_report(board_report, args.format))

    board = board_report.get("board")
    games_shown = board.get("games_shown") if isinstance(board, dict) else None
    if games_shown == 0:
        return 1
    return 0


def cmd_update_ratings(args: argparse.Namespace) -> int:
    history = (
        load_box_scores(args.history, fmt=args.format)
        if args.history
        else []
    )
    if args.games_file:
        new_games = load_box_scores(args.games_file, fmt=args.format)
        report = build_batch_rating_update_report(
            new_games,
            history=history,
            k_factor=args.k_factor,
            home_advantage=args.home_advantage,
            include_leaderboard=args.leaderboard,
        )
    else:
        missing = [
            name
            for name, value in (
                ("--home", args.home),
                ("--away", args.away),
                ("--home-score", args.home_score),
                ("--away-score", args.away_score),
            )
            if value is None
        ]
        if missing:
            print(
                "update-ratings: provide --games-file or "
                + ", ".join(missing),
                file=sys.stderr,
            )
            return 2
        played_on = date.fromisoformat(args.played_on) if args.played_on else None
        game = BoxScore(
            home=args.home,
            away=args.away,
            home_score=args.home_score,
            away_score=args.away_score,
            played_on=played_on,
        )
        report = build_rating_update_report(
            game,
            history=history,
            k_factor=args.k_factor,
            home_advantage=args.home_advantage,
            include_leaderboard=args.leaderboard,
        )
    if args.output == "table":
        print(format_rating_update_table(report))
    else:
        print(json.dumps(report, indent=2))
    return 0


def cmd_ratings(args: argparse.Namespace) -> int:
    scores = load_box_scores(args.file, fmt=args.format)
    report = build_ratings_leaderboard(
        scores,
        k_factor=args.k_factor,
        home_advantage=args.home_advantage,
    )
    if args.output == "table":
        print(format_ratings_table(report))
    else:
        print(json.dumps(report, indent=2))
    return 0


def cmd_standings(args: argparse.Namespace) -> int:
    start = date.fromisoformat(args.start_date) if args.start_date else None
    end = date.fromisoformat(args.end_date) if args.end_date else None
    if (start is None) ^ (end is None):
        print(
            "standings: provide both --start-date and --end-date for filtering",
            file=sys.stderr,
        )
        return 2

    report = load_standings_report(
        args.file,
        fmt=args.format,
        start=start,
        end=end,
        tie_breaker=args.tie_breaker,
    )
    if args.output == "table":
        print(format_standings_table(report))
    else:
        print(json.dumps(report, indent=2))
    return 0


def cmd_season_report(args: argparse.Namespace) -> int:
    start = date.fromisoformat(args.start_date) if args.start_date else None
    end = date.fromisoformat(args.end_date) if args.end_date else None
    if (start is None) ^ (end is None):
        print(
            "season-report: provide both --start-date and --end-date for filtering",
            file=sys.stderr,
        )
        return 2

    report = load_season_report(
        args.file,
        args.team,
        fmt=args.format,
        start=start,
        end=end,
        k_factor=args.k_factor,
    )
    print(json.dumps(report, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "boxscore": cmd_boxscore,
        "elo": cmd_elo,
        "serve": cmd_serve,
        "import-boxscores": cmd_import_boxscores,
        "season-report": cmd_season_report,
        "ratings": cmd_ratings,
        "update-ratings": cmd_update_ratings,
        "standings": cmd_standings,
        "matchups": cmd_matchups,
        "today": cmd_today,
        "board": cmd_board,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
