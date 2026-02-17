from pathlib import Path

import pytest

from sportpulse.config import (
    SportPulseConfig,
    find_config_file,
    load_config,
    resolve_matchups_paths,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_find_config_file_discovers_repo_config():
    assert find_config_file(REPO_ROOT) == REPO_ROOT / "sportpulse.json"


def test_load_config_from_repo_examples():
    config = load_config(REPO_ROOT / "sportpulse.json")

    assert config.matchups_file == (REPO_ROOT / "examples/matchups.json").resolve()
    assert config.history_file == (REPO_ROOT / "examples/season.json").resolve()
    assert config.k_factor == 20.0
    assert config.home_advantage == 65.0
    assert config.points_per_100_elo == 4.0
    assert config.home_court_points == 2.5


def test_load_config_uses_env_overrides(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "sportpulse.json"
    config_path.write_text(
        '{"matchups_file": "slate.json", "history_file": "season.json"}',
        encoding="utf-8",
    )
    (tmp_path / "slate.json").write_text("[]", encoding="utf-8")
    (tmp_path / "season.json").write_text("[]", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPORTPULSE_MATCHUPS_FILE", str(tmp_path / "env-slate.json"))
    monkeypatch.setenv("SPORTPULSE_HISTORY_FILE", str(tmp_path / "env-season.json"))
    (tmp_path / "env-slate.json").write_text("[]", encoding="utf-8")
    (tmp_path / "env-season.json").write_text("[]", encoding="utf-8")

    config = load_config()

    assert config.matchups_file == (tmp_path / "env-slate.json").resolve()
    assert config.history_file == (tmp_path / "env-season.json").resolve()


def test_resolve_matchups_paths_prefers_explicit_cli_paths(tmp_path: Path):
    matchups = tmp_path / "cli-slate.json"
    history = tmp_path / "cli-season.json"
    matchups.write_text("[]", encoding="utf-8")
    history.write_text("[]", encoding="utf-8")

    resolved = resolve_matchups_paths(
        matchups_file=matchups,
        history_file=history,
        config_file=REPO_ROOT / "sportpulse.json",
    )

    assert resolved.matchups_file == matchups.resolve()
    assert resolved.history_file == history.resolve()


def test_load_config_requires_matchups_source(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sportpulse.config._builtin_examples_dir", lambda: None)

    with pytest.raises(FileNotFoundError, match="matchups file not configured"):
        load_config()
