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


def test_matchups_endpoint_returns_projections_with_totals():
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
    assert "projected_total" in game
    assert payload["summary"]["games"] == 2
    assert payload["summary"]["has_scoring_projections"] is True


def test_matchups_endpoint_supports_multi_day_window():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    history_file = EXAMPLES_DIR / "season.json"
    path = (
        f"/matchups?file={matchups_file}&history={history_file}"
        f"&date=2026-01-16&days=2"
    )

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["start_date"] == "2026-01-16"
    assert payload["end_date"] == "2026-01-17"
    assert payload["days"] == 2
    assert len(payload["slates"]) == 2
    assert payload["summary"]["games"] == 3


def test_matchups_endpoint_uses_config_defaults():
    status, payload = _dispatch_get("/matchups?date=2026-01-16")

    assert status == 200
    assert payload["date"] == "2026-01-16"
    assert len(payload["matchups"]) == 2


def test_matchups_endpoint_requires_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sportpulse.config._builtin_examples_dir", lambda: None)

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


def test_today_endpoint_returns_board_projections():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    history_file = EXAMPLES_DIR / "season.json"
    path = (
        f"/today?file={matchups_file}&history={history_file}&date=2026-01-16"
    )

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["title_label"] == "Today"
    assert payload["date"] == "2026-01-16"
    assert "board" in payload
    game = payload["matchups"][0]
    assert "board_pick" in game
    assert "board_confidence" in game
    assert payload["board"]["games_shown"] == 2


def test_today_endpoint_multi_day_board():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    history_file = EXAMPLES_DIR / "season.json"
    path = (
        f"/today?file={matchups_file}&history={history_file}"
        f"&date=2026-01-16&days=2&sort=time"
    )

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["title_label"] == "Today"
    assert payload["days"] == 2
    assert len(payload["slates"]) == 2
    assert payload["board"]["games_shown"] == 3
    assert payload["slates"][0]["matchups"][0]["board_pick"]


def test_today_endpoint_defaults_to_advancing_empty_slate():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    path = f"/today?file={matchups_file}&date=2026-01-15"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["advanced_to_next_slate"] is True
    assert payload["date"] == "2026-01-16"


def test_matchups_endpoint_team_filter():
    matchups_file = EXAMPLES_DIR / "matchups.json"
    path = f"/matchups?file={matchups_file}&date=2026-01-17&team=Lakers"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["team_filter"] == "Lakers"
    assert len(payload["matchups"]) == 1
    assert payload["matchups"][0]["home"] == "Lakers"


def test_ratings_endpoint_returns_leaderboard():
    history_file = EXAMPLES_DIR / "season.json"
    path = f"/ratings?file={history_file}"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["games_replayed"] == 4
    assert payload["ratings"][0]["team"] == "Lakers"
    assert payload["ratings"][0]["rank"] == 1


def test_ratings_endpoint_requires_file():
    status, payload = _dispatch_get("/ratings")

    assert status == 400
    assert "error" in payload


def test_ratings_update_endpoint_applies_new_game():
    history_file = EXAMPLES_DIR / "season.json"
    path = (
        f"/ratings/update?history={history_file}"
        "&home=Lakers&away=Celtics&home_score=120&away_score=100"
        "&played_on=2026-02-01&leaderboard=1"
    )

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["games_replayed"] == 4
    assert payload["updates"]["Lakers"]["after"] > payload["updates"]["Lakers"]["before"]
    assert payload["updates"]["Celtics"]["after"] < payload["updates"]["Celtics"]["before"]
    assert len(payload["ratings"]) == 5


def test_ratings_update_endpoint_requires_game_params():
    status, payload = _dispatch_get("/ratings/update")

    assert status == 400
    assert "error" in payload


def test_ratings_update_endpoint_batch_mode():
    history_file = EXAMPLES_DIR / "season.json"
    path = (
        f"/ratings/update?history={history_file}"
        f"&games_file={history_file}&leaderboard=1"
    )

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["games_replayed"] == 4
    assert payload["games_applied"] == 4
    assert len(payload["game_updates"]) == 4
    assert "Lakers" in payload["net_changes"]
    assert len(payload["ratings"]) == 5


def test_standings_endpoint_returns_table():
    history_file = EXAMPLES_DIR / "season.json"
    path = f"/standings?file={history_file}"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["games_counted"] == 4
    assert payload["standings"][0]["team"] == "Lakers"
    assert payload["standings"][0]["record"]["wins"] == 3


def test_standings_endpoint_date_range():
    history_file = EXAMPLES_DIR / "season.json"
    path = (
        f"/standings?file={history_file}"
        "&start_date=2026-01-11&end_date=2026-01-31"
    )

    status, payload = _dispatch_get(path)

    assert status == 200
    assert payload["games_counted"] == 3
    teams = [row["team"] for row in payload["standings"]]
    assert "Celtics" not in teams


def test_standings_endpoint_requires_file():
    status, payload = _dispatch_get("/standings")

    assert status == 400
    assert "error" in payload


def test_import_boxscores_endpoint_returns_normalized_games():
    history_file = EXAMPLES_DIR / "historical_export.json"
    path = f"/import-boxscores?file={history_file}"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert len(payload) == 4
    assert payload[0]["home"] == "Lakers"
    assert payload[0]["played_on"] == "2026-01-10"


def test_import_boxscores_endpoint_audit_mode():
    history_file = EXAMPLES_DIR / "historical_host_visitor.csv"
    path = f"/import-boxscores?file={history_file}&audit=1"

    status, payload = _dispatch_get(path)

    assert status == 200
    assert len(payload["games"]) == 4
    assert payload["audit"]["format"] == "csv"
    assert "Heat" in payload["audit"]["teams"]


def test_import_boxscores_endpoint_requires_file():
    status, payload = _dispatch_get("/import-boxscores")

    assert status == 400
    assert "error" in payload
