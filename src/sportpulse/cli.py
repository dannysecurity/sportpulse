from __future__ import annotations

import argparse
import json
import sys

from sportpulse.boxscore import BoxScore
from sportpulse.elo import EloCalculator


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "boxscore": cmd_boxscore,
        "elo": cmd_elo,
        "serve": cmd_serve,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
