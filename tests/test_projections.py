from datetime import date
from pathlib import Path

from sportpulse.boxscore import BoxScore
from sportpulse.parsers import load_box_scores
from sportpulse.projections import (
    build_scoring_profiles,
    league_average_ppg,
    project_game_total,
    project_points,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_build_scoring_profiles_from_sample_season():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    profiles = build_scoring_profiles(scores)

    assert profiles["Lakers"].games == 4
    assert profiles["Lakers"].avg_points_for == 107.25
    assert profiles["Celtics"].avg_points_for == 108.0


def test_league_average_ppg_uses_team_offense():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    profiles = build_scoring_profiles(scores)

    assert league_average_ppg(profiles) > 100.0


def test_project_points_blends_offense_and_defense():
    scores = [
        BoxScore("Lakers", "Celtics", 110, 100, date(2026, 1, 10)),
        BoxScore("Warriors", "Lakers", 95, 105, date(2026, 1, 12)),
    ]
    profiles = build_scoring_profiles(scores)

    home_points, away_points = project_points("Lakers", "Warriors", profiles)

    assert home_points > away_points
    assert home_points + away_points > 180.0


def test_project_game_total_returns_over_under():
    scores = load_box_scores(EXAMPLES_DIR / "season.json")
    profiles = build_scoring_profiles(scores)

    totals = project_game_total("Lakers", "Celtics", profiles)

    assert totals["home_projected_points"] > 0
    assert totals["away_projected_points"] > 0
    assert totals["projected_total"] == round(
        totals["home_projected_points"] + totals["away_projected_points"],
        1,
    )
