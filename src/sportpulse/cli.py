from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from sportpulse.boxscore import BoxScore
from sportpulse.elo import EloCalculator
from sportpulse.matchups import build_matchups_report, load_matchups
from sportpulse.parsers import box_scores_to_json, load_box_scores
from sportpulse.season import build_season_report


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

    matchups = sub.add_parser(
        "matchups",
        help="Show today's slate with odds-lite ELO win probabilities",
    )
    matchups.add_argument("--file", required=True, help="Path to scheduled matchups JSON")
    matchups.add_argument(
        "--history",
        help="Optional JSON or CSV season file for ELO ratings (defaults to 1500)",
    )
    matchups.add_argument(
        "--date",
        help="Calendar day to show (ISO, defaults to today)",
    )
    matchups.add_argument("--k-factor", type=float, default=20.0)
    matchups.add_argument(
        "--home-advantage",
        type=float,
        default=65.0,
        help="ELO points added for the home team in projections",
    )

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
    slate = load_matchups(args.file)
    history = load_box_scores(args.history) if args.history else None
    report = build_matchups_report(
        slate,
        on_date=on_date,
        history=history,
        k_factor=args.k_factor,
        home_advantage=args.home_advantage,
    )
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
        "matchups": cmd_matchups,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
