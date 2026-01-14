from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from sportpulse.boxscore import BoxScore
from sportpulse.elo import EloCalculator


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

        self._send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = HTTPServer((host, port), SportPulseHandler)
    print(f"SportPulse API listening on http://{host}:{port}")
    server.serve_forever()
