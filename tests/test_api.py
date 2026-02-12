import json
from pathlib import Path

from sportpulse.api import SportPulseHandler

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


class _FakeResponse:
    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: dict[str, str] = {}
        self.body = b""

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def end_headers(self) -> None:
        pass

    def write(self, data: bytes) -> None:
        self.body += data


def _dispatch_get(path: str) -> tuple[int, dict[str, object]]:
    handler = SportPulseHandler.__new__(SportPulseHandler)
    handler.path = path
    response = _FakeResponse()
    handler.send_response = response.send_response  # type: ignore[method-assign]
    handler.send_header = response.send_header  # type: ignore[method-assign]
    handler.end_headers = response.end_headers  # type: ignore[method-assign]
    handler.wfile = response  # type: ignore[assignment]
    handler.do_GET()
    payload = json.loads(response.body.decode("utf-8"))
    assert response.status is not None
    return response.status, payload


def test_matchups_endpoint_returns_projections():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    history_file = EXAMPLES_DIR / "season.json"
    path = (
        f"/matchups?file={matchups_file}&history={history_file}&date=2026-01-16"
    )

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["date"] == "2026-01-16"
    assert len(payload["matchups"]) == 2
    game = payload["matchups"][0]
    assert "home_moneyline" in game
    assert "home_spread" in game


def test_matchups_endpoint_requires_file():
    status, payload = _dispatch_get("/matchups")

    assert status == 400
    assert "error" in payload


def test_matchups_endpoint_advances_to_next_slate():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    path = f"/matchups?file={matchups_file}&date=2026-01-15&next=1"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["requested_date"] == "2026-01-15"
    assert payload["date"] == "2026-01-16"
    assert payload["advanced_to_next_slate"] is True


def test_matchups_endpoint_team_filter():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    path = f"/matchups?file={matchups_file}&date=2026-01-17&team=Lakers"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["team_filter"] == "Lakers"
    assert len(payload["matchups"]) == 1
    assert payload["matchups"][0]["home"] == "Lakers"
