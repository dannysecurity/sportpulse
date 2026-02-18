from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from sportpulse.boxscore import BoxScore
from sportpulse.config import resolve_matchups_paths
from sportpulse.elo import EloCalculator
from sportpulse.matchups import (
    build_matchups_report,
    format_matchups_table,
    load_matchups,
)
from sportpulse.parsers import box_scores_to_json, load_box_scores
from sportpulse.ratings import build_ratings_leaderboard, format_ratings_table
from sportpulse.season import build_season_report
from sportpulse.standings import build_standings_report, format_standings_table


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
        "--format",
        choices=("json", "table"),
        default="json",
        help="Output format (json or human-readable table)",
    )


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
        help="Parse historical box scores from a JSON or CSV file",
    )
    import_scores.add_argument("--file", required=True, help="Path to the input file")
    import_scores.add_argument(
        "--format",
        choices=("json", "csv"),
        help="Input format (defaults to the file extension)",
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
    scores = load_box_scores(args.file, fmt=args.format)
    print(json.dumps(box_scores_to_json(scores), indent=2))
    return 0


def cmd_matchups(args: argparse.Namespace) -> int:
    on_date = date.fromisoformat(args.date) if args.date else date.today()
    try:
        paths = resolve_matchups_paths(
            matchups_file=args.file,
            history_file=args.history,
            config_file=args.config,
        )
    except FileNotFoundError as exc:
        print(f"matchups: {exc}", file=sys.stderr)
        return 2

    slate = load_matchups(paths.matchups_file)
    history = load_box_scores(paths.history_file) if paths.history_file else None
    if history is None:
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
    report = build_matchups_report(
        slate,
        on_date=on_date,
        history=history,
        k_factor=k_factor,
        home_advantage=home_advantage,
        points_per_100_elo=points_per_100_elo,
        home_court_points=home_court_points,
        advance_if_empty=args.next if args.next is not None else False,
        team=args.team,
    )
    if args.format == "table":
        print(format_matchups_table(report))
    else:
        print(json.dumps(report, indent=2))

    summary = report.get("summary")
    if isinstance(summary, dict) and summary.get("games", 0) == 0:
        return 1
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

    scores = load_box_scores(args.file, fmt=args.format)
    report = build_standings_report(
        scores,
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

    scores = load_box_scores(args.file, fmt=args.format)
    report = build_season_report(
        args.team,
        scores,
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
        "standings": cmd_standings,
        "matchups": cmd_matchups,
        "today": cmd_matchups,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
