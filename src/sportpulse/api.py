from __future__ import annotations

import json
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sportpulse.boxscore import BoxScore
from sportpulse.config import resolve_matchups_paths
from sportpulse.board import build_today_board_report
from sportpulse.elo import EloCalculator
from sportpulse.schedule_cache import load_matchups_report, load_standings_report
from sportpulse.parsers import (
    box_scores_to_json,
    import_box_scores_with_audit,
    load_box_scores,
)
from sportpulse.ratings import (
    build_batch_rating_update_report,
    build_rating_update_report,
    build_ratings_leaderboard,
)


class SportPulseHandler(BaseHTTPRequestHandler):
    """Minimal JSON API for box scores and ELO calculations."""

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if parsed.path == "/boxscore":
            params = parse_qs(parsed.query)
            try:
                score = BoxScore(
                    home=params["home"][0],
                    away=params["away"][0],
                    home_score=int(params["home_score"][0]),
                    away_score=int(params["away_score"][0]),
                )
            except (KeyError, IndexError, ValueError):
                self._send_json(400, {"error": "missing or invalid query parameters"})
                return
            self._send_json(200, score.summary())
            return

        if parsed.path == "/elo":
            params = parse_qs(parsed.query)
            try:
                calc = EloCalculator(k_factor=float(params.get("k_factor", ["20"])[0]))
                new_a, new_b = calc.update(
                    float(params["rating_a"][0]),
                    float(params["rating_b"][0]),
                    score_a=int(params["score_a"][0]),
                    score_b=int(params["score_b"][0]),
                )
            except (KeyError, IndexError, ValueError):
                self._send_json(400, {"error": "missing or invalid query parameters"})
                return
            self._send_json(
                200,
                {
                    "team_a": {"after": new_a},
                    "team_b": {"after": new_b},
                },
            )
            return

        if parsed.path == "/matchups":
            params = parse_qs(parsed.query)
            try:
                file_param = params.get("file", [None])[0]
                history_param = params.get("history", [None])[0]
                config_param = params.get("config", [None])[0]
                paths = resolve_matchups_paths(
                    matchups_file=file_param,
                    history_file=history_param,
                    config_file=config_param,
                )
                on_date = date.fromisoformat(params.get("date", [date.today().isoformat()])[0])
                k_factor = float(params.get("k_factor", [str(paths.k_factor)])[0])
                home_advantage = float(
                    params.get("home_advantage", [str(paths.home_advantage)])[0]
                )
                points_per_100_elo = float(
                    params.get(
                        "points_per_100_elo",
                        [str(paths.points_per_100_elo)],
                    )[0]
                )
                home_court_points = float(
                    params.get(
                        "home_court_points",
                        [str(paths.home_court_points)],
                    )[0]
                )
                advance_if_empty = params.get("next", ["0"])[0].lower() in ("1", "true", "yes")
                team = params.get("team", [None])[0]
                days = int(params.get("days", ["1"])[0])
                if days < 1:
                    raise ValueError("days must be at least 1")
                report = load_matchups_report(
                    paths.matchups_file,
                    on_date=on_date,
                    history_file=paths.history_file,
                    k_factor=k_factor,
                    home_advantage=home_advantage,
                    points_per_100_elo=points_per_100_elo,
                    home_court_points=home_court_points,
                    advance_if_empty=advance_if_empty,
                    team=team,
                    days=days,
                )
            except (KeyError, IndexError, ValueError, FileNotFoundError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, report)
            return

        if parsed.path == "/today":
            params = parse_qs(parsed.query)
            try:
                file_param = params.get("file", [None])[0]
                history_param = params.get("history", [None])[0]
                config_param = params.get("config", [None])[0]
                paths = resolve_matchups_paths(
                    matchups_file=file_param,
                    history_file=history_param,
                    config_file=config_param,
                )
                on_date = date.fromisoformat(params.get("date", [date.today().isoformat()])[0])
                k_factor = float(params.get("k_factor", [str(paths.k_factor)])[0])
                home_advantage = float(
                    params.get("home_advantage", [str(paths.home_advantage)])[0]
                )
                points_per_100_elo = float(
                    params.get(
                        "points_per_100_elo",
                        [str(paths.points_per_100_elo)],
                    )[0]
                )
                home_court_points = float(
                    params.get(
                        "home_court_points",
                        [str(paths.home_court_points)],
                    )[0]
                )
                advance_if_empty = params.get("next", ["1"])[0].lower() in ("1", "true", "yes")
                team = params.get("team", [None])[0]
                days = int(params.get("days", ["1"])[0])
                if days < 1:
                    raise ValueError("days must be at least 1")
                sort_by = params.get("sort", ["time"])[0]
                if sort_by not in ("spread", "confidence", "total", "matchup", "time"):
                    raise ValueError(
                        "sort must be spread, confidence, total, matchup, or time"
                    )
                min_spread_param = params.get("min_spread", [None])[0]
                min_spread = float(min_spread_param) if min_spread_param is not None else None
                confidence = params.get("confidence", [None])[0]
                if confidence is not None and confidence not in (
                    "toss_up",
                    "lean",
                    "strong",
                ):
                    raise ValueError("confidence must be toss_up, lean, or strong")
                report = load_matchups_report(
                    paths.matchups_file,
                    on_date=on_date,
                    history_file=paths.history_file,
                    k_factor=k_factor,
                    home_advantage=home_advantage,
                    points_per_100_elo=points_per_100_elo,
                    home_court_points=home_court_points,
                    advance_if_empty=advance_if_empty,
                    team=team,
                    days=days,
                )
                report = build_today_board_report(
                    report,
                    sort_by=sort_by,  # type: ignore[arg-type]
                    min_spread=min_spread,
                    confidence=confidence,  # type: ignore[arg-type]
                )
            except (KeyError, IndexError, ValueError, FileNotFoundError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, report)
            return

        if parsed.path == "/import-boxscores":
            params = parse_qs(parsed.query)
            try:
                file_param = params.get("file", [None])[0]
                if not file_param:
                    raise ValueError("file query parameter is required")
                fmt_param = params.get("format", [None])[0]
                audit_param = params.get("audit", ["0"])[0].lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if audit_param:
                    scores, audit = import_box_scores_with_audit(
                        file_param,
                        fmt=fmt_param,
                    )
                    payload: object = {
                        "games": box_scores_to_json(scores),
                        "audit": audit.to_dict(),
                    }
                else:
                    scores = load_box_scores(file_param, fmt=fmt_param)
                    payload = box_scores_to_json(scores)
            except (KeyError, IndexError, ValueError, FileNotFoundError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, payload)
            return

        if parsed.path == "/ratings":
            params = parse_qs(parsed.query)
            try:
                file_param = params.get("file", [None])[0]
                if not file_param:
                    raise ValueError("file query parameter is required")
                k_factor = float(params.get("k_factor", ["20"])[0])
                home_advantage = float(params.get("home_advantage", ["0"])[0])
                scores = load_box_scores(file_param)
                report = build_ratings_leaderboard(
                    scores,
                    k_factor=k_factor,
                    home_advantage=home_advantage,
                )
            except (KeyError, IndexError, ValueError, FileNotFoundError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, report)
            return

        if parsed.path == "/ratings/update":
            params = parse_qs(parsed.query)
            try:
                history_param = params.get("history", [None])[0]
                history = load_box_scores(history_param) if history_param else []
                k_factor = float(params.get("k_factor", ["20"])[0])
                home_advantage = float(params.get("home_advantage", ["0"])[0])
                include_leaderboard = params.get("leaderboard", ["0"])[0].lower() in (
                    "1",
                    "true",
                    "yes",
                )
                games_file = params.get("games_file", [None])[0]
                if games_file:
                    new_games = load_box_scores(games_file)
                    report = build_batch_rating_update_report(
                        new_games,
                        history=history,
                        k_factor=k_factor,
                        home_advantage=home_advantage,
                        include_leaderboard=include_leaderboard,
                    )
                else:
                    played_on_param = params.get("played_on", [None])[0]
                    played_on = date.fromisoformat(played_on_param) if played_on_param else None
                    game = BoxScore(
                        home=params["home"][0],
                        away=params["away"][0],
                        home_score=int(params["home_score"][0]),
                        away_score=int(params["away_score"][0]),
                        played_on=played_on,
                    )
                    report = build_rating_update_report(
                        game,
                        history=history,
                        k_factor=k_factor,
                        home_advantage=home_advantage,
                        include_leaderboard=include_leaderboard,
                    )
            except (KeyError, IndexError, ValueError, FileNotFoundError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, report)
            return

        if parsed.path == "/standings":
            params = parse_qs(parsed.query)
            try:
                file_param = params.get("file", [None])[0]
                if not file_param:
                    raise ValueError("file query parameter is required")
                start_param = params.get("start_date", [None])[0]
                end_param = params.get("end_date", [None])[0]
                start = date.fromisoformat(start_param) if start_param else None
                end = date.fromisoformat(end_param) if end_param else None
                if (start is None) ^ (end is None):
                    raise ValueError(
                        "provide both start_date and end_date for filtering"
                    )
                tie_breaker = params.get("tie_breaker", ["win_pct"])[0]
                if tie_breaker not in ("win_pct", "point_diff", "team_name"):
                    raise ValueError("tie_breaker must be win_pct, point_diff, or team_name")
                report = load_standings_report(
                    file_param,
                    start=start,
                    end=end,
                    tie_breaker=tie_breaker,  # type: ignore[arg-type]
                )
            except (KeyError, IndexError, ValueError, FileNotFoundError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, report)
            return

        self._send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = HTTPServer((host, port), SportPulseHandler)
    print(f"SportPulse API listening on http://{host}:{port}")
    server.serve_forever()
