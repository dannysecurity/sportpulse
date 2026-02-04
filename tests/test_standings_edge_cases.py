"""Edge-case tests for league-wide stat aggregation and standings."""

from datetime import date

import pytest

from sportpulse.models import GameResult
from sportpulse.rollup import ParticipationPolicy, TeamStats
from sportpulse.standings import (
    VenueSplit,
    aggregate_standings,
    discover_teams,
    games_for_teams,
    head_to_head_record,
    rank_standings,
    standings_in_range,
    venue_split,
)
from sportpulse.stats import TeamRecord


def _game(
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    *,
    played_on: date | None = None,
) -> GameResult:
    return GameResult(home, away, home_score, away_score, played_on=played_on)


def test_discover_teams_empty_input():
    assert discover_teams([]) == frozenset()


def test_discover_teams_deduplicates_and_collects_both_sides():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105),
        _game("Celtics", "Warriors", 101, 99),
    ]
    assert discover_teams(games) == frozenset({"Lakers", "Celtics", "Warriors"})


def test_aggregate_standings_empty_schedule():
    assert aggregate_standings([]) == {}


def test_aggregate_standings_single_game_two_team_mirror_records():
    games = [_game("Lakers", "Celtics", 110, 100)]
    standings = aggregate_standings(games)
    assert set(standings) == {"Lakers", "Celtics"}
    assert standings["Lakers"].record == TeamRecord(wins=1, losses=0, ties=0)
    assert standings["Celtics"].record == TeamRecord(wins=0, losses=1, ties=0)
    assert standings["Lakers"].point_differential == 10
    assert standings["Celtics"].point_differential == -10


def test_aggregate_standings_three_team_round_robin():
    games = [
        _game("A", "B", 100, 90),
        _game("B", "C", 80, 85),
        _game("C", "A", 95, 95),
    ]
    standings = aggregate_standings(games)
    assert standings["A"].record == TeamRecord(wins=1, losses=0, ties=1)
    assert standings["B"].record == TeamRecord(wins=0, losses=2, ties=0)
    assert standings["C"].record == TeamRecord(wins=1, losses=0, ties=1)
    assert sum(s.point_differential for s in standings.values()) == 0


def test_aggregate_standings_all_ties_league():
    games = [
        _game("A", "B", 100, 100),
        _game("B", "C", 50, 50),
        _game("C", "A", 0, 0),
    ]
    standings = aggregate_standings(games)
    for stats in standings.values():
        assert stats.record == TeamRecord(wins=0, losses=0, ties=2)
        assert stats.point_differential == 0
        assert stats.avg_margin == 0.0


def test_standings_in_range_excludes_undated_games():
    games = [
        _game("Lakers", "Celtics", 110, 105),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 12)),
        _game("Lakers", "Suns", 101, 99, played_on=date(2026, 1, 20)),
    ]
    ranged = standings_in_range(games, date(2026, 1, 1), date(2026, 1, 31))
    assert ranged["Lakers"].record == TeamRecord(wins=2, losses=0, ties=0)
    assert "Celtics" not in ranged
    assert ranged["Warriors"].record == TeamRecord(wins=0, losses=1, ties=0)


def test_standings_in_range_empty_when_start_after_end():
    games = [_game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10))]
    assert standings_in_range(games, date(2026, 2, 1), date(2026, 1, 1)) == {}


def test_rank_standings_win_pct_with_point_diff_tiebreaker():
    standings = {
        "A": TeamStats(
            record=TeamRecord(wins=2, losses=1, ties=0),
            point_differential=15,
            games_in_record=3,
            games_in_point_diff=3,
        ),
        "B": TeamStats(
            record=TeamRecord(wins=1, losses=2, ties=0),
            point_differential=5,
            games_in_record=3,
            games_in_point_diff=3,
        ),
        "C": TeamStats(
            record=TeamRecord(wins=1, losses=2, ties=0),
            point_differential=-20,
            games_in_record=3,
            games_in_point_diff=3,
        ),
    }
    ranked = rank_standings(standings)
    assert [row.team for row in ranked] == ["A", "B", "C"]
    assert ranked[0].win_pct == pytest.approx(2 / 3)
    assert ranked[1].win_pct == pytest.approx(1 / 3)
    assert ranked[2].win_pct == pytest.approx(1 / 3)
    assert ranked[1].point_differential > ranked[2].point_differential


def test_rank_standings_tied_win_pct_and_point_diff_sorts_by_name():
    standings = {
        "Zebra": TeamStats(
            record=TeamRecord(wins=1, losses=1, ties=0),
            point_differential=0,
            games_in_record=2,
            games_in_point_diff=2,
        ),
        "Alpha": TeamStats(
            record=TeamRecord(wins=1, losses=1, ties=0),
            point_differential=0,
            games_in_record=2,
            games_in_point_diff=2,
        ),
    }
    ranked = rank_standings(standings)
    assert [row.team for row in ranked] == ["Alpha", "Zebra"]


def test_rank_standings_point_diff_primary_tie_breaker():
    standings = aggregate_standings(
        [
            _game("A", "B", 120, 100),
            _game("A", "C", 90, 100),
            _game("B", "C", 100, 100),
        ]
    )
    ranked = rank_standings(standings, tie_breaker="point_diff")
    assert ranked[0].team == "A"
    assert ranked[0].point_differential == 10


def test_rank_standings_team_name_only():
    standings = aggregate_standings([_game("Lakers", "Celtics", 110, 100)])
    ranked = rank_standings(standings, tie_breaker="team_name")
    assert [row.team for row in ranked] == ["Celtics", "Lakers"]


def test_head_to_head_no_meetings_returns_empty_record():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Suns", 99, 102),
    ]
    assert head_to_head_record("Lakers", "Warriors", games) == TeamRecord()


def test_head_to_head_only_counts_mutual_matchups():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105),
        _game("Celtics", "Warriors", 101, 99),
    ]
    assert head_to_head_record("Lakers", "Celtics", games) == TeamRecord(
        wins=1, losses=0, ties=0
    )
    assert head_to_head_record("Lakers", "Warriors", games) == TeamRecord(
        wins=1, losses=0, ties=0
    )
    assert head_to_head_record("Celtics", "Warriors", games) == TeamRecord(
        wins=1, losses=0, ties=0
    )


def test_head_to_head_includes_ties():
    games = [
        _game("Lakers", "Celtics", 100, 100),
        _game("Celtics", "Lakers", 98, 98),
    ]
    record = head_to_head_record("Lakers", "Celtics", games)
    assert record == TeamRecord(wins=0, losses=0, ties=2)


def test_head_to_head_duplicate_games_double_count():
    game = _game("Lakers", "Celtics", 110, 100)
    games = [game, game]
    assert head_to_head_record("Lakers", "Celtics", games) == TeamRecord(
        wins=2, losses=0, ties=0
    )


def test_venue_split_home_only_schedule():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Lakers", "Warriors", 105, 95),
    ]
    split = venue_split("Lakers", games)
    assert split == VenueSplit(
        home=TeamRecord(wins=2, losses=0, ties=0),
        away=TeamRecord(),
    )
    assert split.combined == TeamRecord(wins=2, losses=0, ties=0)


def test_venue_split_away_only_schedule():
    games = [
        _game("Celtics", "Lakers", 110, 100),
        _game("Warriors", "Lakers", 95, 105),
    ]
    split = venue_split("Lakers", games)
    assert split.home == TeamRecord()
    assert split.away == TeamRecord(wins=1, losses=1, ties=0)
    assert split.combined == TeamRecord(wins=1, losses=1, ties=0)


def test_venue_split_combined_matches_full_aggregate():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Lakers", 95, 105),
        _game("Lakers", "Suns", 98, 98),
    ]
    split = venue_split("Lakers", games)
    standings = aggregate_standings(games)["Lakers"].record
    assert split.combined == standings


def test_venue_split_non_participant_games_do_not_affect_either_side():
    games = [_game("Celtics", "Warriors", 105, 99)]
    split = venue_split("Lakers", games)
    assert split == VenueSplit(home=TeamRecord(), away=TeamRecord())
    assert split.combined == TeamRecord()


def test_case_sensitive_team_names_treated_as_distinct_teams():
    games = [_game("Lakers", "Celtics", 110, 100)]
    standings = aggregate_standings(games)
    assert "Lakers" in standings
    assert "lakers" not in standings
    assert head_to_head_record("lakers", "Celtics", games) == TeamRecord()


def test_duplicate_games_inflate_standings_for_both_teams():
    game = _game("Lakers", "Celtics", 110, 100, played_on=date(2026, 1, 10))
    games = [game, game]
    standings = aggregate_standings(games)
    assert standings["Lakers"].record.games_played == 2
    assert standings["Celtics"].record.games_played == 2
    assert standings["Lakers"].point_differential == 20


def test_games_for_teams_filters_subset():
    games = [
        _game("Lakers", "Celtics", 110, 100),
        _game("Warriors", "Suns", 99, 102),
        _game("Celtics", "Warriors", 101, 99),
    ]
    filtered = games_for_teams(games, ["Lakers", "Celtics"])
    assert filtered == [games[0], games[2]]


def test_games_for_teams_empty_team_list_returns_empty():
    games = [_game("Lakers", "Celtics", 110, 100)]
    assert games_for_teams(games, []) == []


def test_monthly_partition_invariant_per_team():
    games = [
        _game("Lakers", "Celtics", 110, 105, played_on=date(2026, 1, 10)),
        _game("Warriors", "Lakers", 99, 102, played_on=date(2026, 1, 20)),
        _game("Lakers", "Suns", 98, 98, played_on=date(2026, 2, 5)),
        _game("Nuggets", "Lakers", 120, 100, played_on=date(2026, 2, 15)),
    ]
    january = standings_in_range(games, date(2026, 1, 1), date(2026, 1, 31))
    february = standings_in_range(games, date(2026, 2, 1), date(2026, 2, 28))
    full = aggregate_standings(games)
    for team in discover_teams(games):
        jan = january.get(team, TeamStats(TeamRecord(), 0, 0, 0))
        feb = february.get(team, TeamStats(TeamRecord(), 0, 0, 0))
        season = full[team]
        assert jan.record + feb.record == season.record
        assert jan.point_differential + feb.point_differential == season.point_differential


def test_count_all_policy_not_used_in_league_standings_by_default():
    """Participant-only is the default; non-participant phantom losses stay isolated."""
    games = [
        _game("Celtics", "Warriors", 105, 99),
        _game("Lakers", "Suns", 110, 100),
    ]
    default = aggregate_standings(games)
    count_all = aggregate_standings(games, policy=ParticipationPolicy.COUNT_ALL)
    assert default["Lakers"].record == TeamRecord(wins=1, losses=0, ties=0)
    assert count_all["Lakers"].record == TeamRecord(wins=1, losses=1, ties=0)
    assert default["Celtics"].record == TeamRecord(wins=1, losses=0, ties=0)
    assert count_all["Celtics"].record == TeamRecord(wins=1, losses=1, ties=0)


def test_negative_scores_propagate_through_standings():
    games = [_game("Lakers", "Celtics", -5, -10)]
    standings = aggregate_standings(games)
    assert standings["Lakers"].record == TeamRecord(wins=1, losses=0, ties=0)
    assert standings["Lakers"].point_differential == 5
    assert standings["Celtics"].point_differential == -5


def test_generator_input_supported_for_standings():
    def game_stream():
        yield _game("Lakers", "Celtics", 110, 100)
        yield _game("Warriors", "Lakers", 95, 105)

    standings = aggregate_standings(game_stream())
    assert standings["Lakers"].record == TeamRecord(wins=2, losses=0, ties=0)


def test_whitespace_team_name_does_not_match_in_standings():
    games = [_game(" Lakers ", "Celtics", 110, 100)]
    standings = aggregate_standings(games)
    assert "Lakers" not in standings
    assert " Lakers " in standings
    assert standings[" Lakers "].record == TeamRecord(wins=1, losses=0, ties=0)


def test_rank_standings_empty_dict():
    assert rank_standings({}) == []


def test_undefeated_and_winless_teams_in_same_standings():
    games = [
        _game("A", "B", 100, 80),
        _game("A", "C", 110, 90),
        _game("A", "D", 105, 85),
        _game("B", "C", 95, 100),
        _game("B", "D", 92, 98),
        _game("C", "D", 101, 99),
    ]
    standings = aggregate_standings(games)
    assert standings["A"].record == TeamRecord(wins=3, losses=0, ties=0)
    assert standings["B"].record == TeamRecord(wins=0, losses=3, ties=0)
    assert standings["C"].record == TeamRecord(wins=2, losses=1, ties=0)
    assert standings["D"].record == TeamRecord(wins=1, losses=2, ties=0)
    ranked = rank_standings(standings)
    assert ranked[0].team == "A"
    assert ranked[0].win_pct == pytest.approx(1.0)
    assert ranked[-1].team == "B"
    assert ranked[-1].win_pct == pytest.approx(0.0)
