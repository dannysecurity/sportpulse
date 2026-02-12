from __future__ import annotations

import json
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sportpulse.boxscore import BoxScore
from sportpulse.elo import EloCalculator
from sportpulse.matchups import build_matchups_report, load_matchups
from sportpulse.parsers import load_box_scores


class SportPulseHandler(BaseHTTPRequestHandler):
    """Minimal JSON API for box scores and ELO calculations."""

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
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
                file_path = params["file"][0]
                on_date = date.fromisoformat(params.get("date", [date.today().isoformat()])[0])
                slate = load_matchups(Path(file_path))
                history_param = params.get("history", [None])[0]
                history = load_box_scores(history_param) if history_param else None
                k_factor = float(params.get("k_factor", ["20"])[0])
                home_advantage = float(params.get("home_advantage", ["65"])[0])
                advance_if_empty = params.get("next", ["0"])[0].lower() in ("1", "true", "yes")
                team = params.get("team", [None])[0]
                report = build_matchups_report(
                    slate,
                    on_date=on_date,
                    history=history,
                    k_factor=k_factor,
                    home_advantage=home_advantage,
                    advance_if_empty=advance_if_empty,
                    team=team,
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
