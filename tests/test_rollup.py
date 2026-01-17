from datetime import date

from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, aggregate_team_stats
from sportpulse.schedule import Schedule
from sportpulse.season import build_season_report
from sportpulse.stats import TeamRecord


def test_schedule_team_stats_matches_participant_only_rollup():
    sched = Schedule(team="Lakers")
    sched.add(GameResult("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)))
    sched.add(GameResult("Warriors", "Lakers", 120, 100, played_on=date(2026, 1, 12)))

    stats = sched.team_stats()
    expected = aggregate_team_stats(
        "Lakers", sched.games, policy=ParticipationPolicy.PARTICIPANT_ONLY
    )
    assert stats == expected
    assert stats.record == TeamRecord(wins=1, losses=1, ties=0)
    assert stats.point_differential == -15


def test_schedule_point_diff_helpers():
    sched = Schedule(team="Lakers")
    sched.add(GameResult("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10)))
    sched.add(GameResult("Warriors", "Lakers", 95, 105, played_on=date(2026, 2, 5)))

    assert sched.point_diff() == 20
    assert sched.point_diff_in_range(date(2026, 1, 1), date(2026, 1, 31)) == 10


def test_season_report_includes_point_differential_fields():
    from pathlib import Path

    from sportpulse.parsers import load_box_scores

    examples = Path(__file__).resolve().parents[1] / "examples"
    scores = load_box_scores(examples / "season.json")
    report = build_season_report(
        "Lakers",
        scores,
        start=date(2026, 1, 11),
        end=date(2026, 1, 31),
    )

    assert report["point_differential"] == 11
    assert report["point_differential_in_range"] == 7
    assert report["stats_in_range"]["point_differential"] == 7
    assert report["stats_in_range"]["record"] == report["record_in_range"]
