from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_CONFIG_FILENAMES = (".sportpulse.json", "sportpulse.json")


@dataclass(frozen=True)
class SportPulseConfig:
    """Resolved data paths and projection defaults for the today board."""

    matchups_file: Path
    history_file: Path | None = None
    k_factor: float = 20.0
    home_advantage: float = 65.0
    points_per_100_elo: float = 4.0
    home_court_points: float = 2.5


def _builtin_examples_dir() -> Path | None:
    """Return the bundled examples directory when it exists on disk."""
    candidates = [
        Path(__file__).resolve().parents[2] / "examples",
        Path.cwd() / "examples",
    ]
    for candidate in candidates:
        if (candidate / "matchups.json").is_file():
            return candidate
    return None


def find_config_file(start: Path | None = None) -> Path | None:
    """Walk upward from ``start`` (or cwd) looking for a SportPulse config file."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        for name in _CONFIG_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _load_config_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"config file must be a JSON object: {path}")
    return payload


def load_config(config_path: Path | None = None) -> SportPulseConfig:
    """Load SportPulse settings from a config file, environment, or bundled examples."""
    path = config_path or find_config_file()
    base = path.parent.resolve() if path is not None else Path.cwd()

    payload: dict[str, object] = _load_config_payload(path) if path is not None else {}

    matchups_raw = os.environ.get("SPORTPULSE_MATCHUPS_FILE") or payload.get("matchups_file")
    history_raw = os.environ.get("SPORTPULSE_HISTORY_FILE") or payload.get("history_file")

    examples = _builtin_examples_dir()
    if matchups_raw is None and examples is not None:
        matchups_raw = str(examples / "matchups.json")
    if history_raw is None and examples is not None:
        history_raw = str(examples / "season.json")

    if not isinstance(matchups_raw, str) or not matchups_raw:
        raise FileNotFoundError(
            "matchups file not configured: pass --file, set SPORTPULSE_MATCHUPS_FILE, "
            "or create sportpulse.json with a matchups_file entry"
        )

    matchups_file = _resolve_path(matchups_raw, base)
    if not matchups_file.is_file():
        raise FileNotFoundError(f"matchups file not found: {matchups_file}")

    history_file: Path | None = None
    if isinstance(history_raw, str) and history_raw:
        history_file = _resolve_path(history_raw, base)
        if not history_file.is_file():
            raise FileNotFoundError(f"history file not found: {history_file}")

    k_factor = float(payload.get("k_factor", 20.0))
    home_advantage = float(payload.get("home_advantage", 65.0))
    points_per_100_elo = float(payload.get("points_per_100_elo", 4.0))
    home_court_points = float(payload.get("home_court_points", 2.5))

    return SportPulseConfig(
        matchups_file=matchups_file,
        history_file=history_file,
        k_factor=k_factor,
        home_advantage=home_advantage,
        points_per_100_elo=points_per_100_elo,
        home_court_points=home_court_points,
    )


def resolve_matchups_paths(
    *,
    matchups_file: str | Path | None = None,
    history_file: str | Path | None = None,
    config_file: str | Path | None = None,
) -> SportPulseConfig:
    """Merge explicit CLI paths with config defaults and environment overrides."""
    config = load_config(Path(config_file) if config_file else None)

    resolved_matchups = Path(matchups_file).resolve() if matchups_file else config.matchups_file
    if not resolved_matchups.is_file():
        raise FileNotFoundError(f"matchups file not found: {resolved_matchups}")

    resolved_history: Path | None
    if history_file is not None:
        resolved_history = Path(history_file).resolve()
        if not resolved_history.is_file():
            raise FileNotFoundError(f"history file not found: {resolved_history}")
    else:
        resolved_history = config.history_file

    return SportPulseConfig(
        matchups_file=resolved_matchups,
        history_file=resolved_history,
        k_factor=config.k_factor,
        home_advantage=config.home_advantage,
        points_per_100_elo=config.points_per_100_elo,
        home_court_points=config.home_court_points,
    )
