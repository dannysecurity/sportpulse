from datetime import date

from sportpulse.elo import EloCalculator, expected_score
from sportpulse.models import EloRating


def test_expected_score_symmetry():
    assert expected_score(1500, 1500) == 0.5
    assert expected_score(1600, 1400) > 0.5


def test_elo_update_favors_winner():
    calc = EloCalculator(k_factor=20)
    new_a, new_b = calc.update(1500, 1500, score_a=110, score_b=100)
    assert new_a > 1500
    assert new_b < 1500


def test_apply_result_tracks_history():
    calc = EloCalculator()
    ratings: dict[str, EloRating] = {}
    calc.apply_result(ratings, "Lakers", "Celtics", 112, 108, date(2026, 1, 14))

    assert "Lakers" in ratings
    assert ratings["Lakers"].games_played == 1
    assert len(ratings["Lakers"].history) == 1


def test_elo_tie_at_equal_ratings_is_neutral():
    calc = EloCalculator(k_factor=20)
    new_a, new_b = calc.update(1500, 1500, score_a=110, score_b=110)
    assert new_a == 1500
    assert new_b == 1500


def test_elo_update_is_zero_sum():
    calc = EloCalculator(k_factor=20)
    rating_a, rating_b = 1580, 1620
    new_a, new_b = calc.update(rating_a, rating_b, score_a=112, score_b=108)
    assert round(new_a - rating_a + new_b - rating_b, 1) == 0.0


def test_margin_multiplier_scales_blowout_updates():
    calc = EloCalculator(k_factor=20)
    close_a, _ = calc.update(1500, 1500, score_a=101, score_b=100)
    blowout_a, _ = calc.update(1500, 1500, score_a=130, score_b=100)
    assert calc.margin_multiplier(101, 100) == 1.0
    assert calc.margin_multiplier(130, 100) > 1.0
    assert blowout_a - 1500 > close_a - 1500


def test_home_advantage_reduces_home_win_rating_gain():
    calc = EloCalculator(k_factor=20, home_advantage=65)
    home_win, _ = calc.update(1500, 1500, score_a=110, score_b=100, team_a_home=True)
    away_win, _ = calc.update(1500, 1500, score_a=110, score_b=100, team_a_home=False)
    assert away_win - 1500 > home_win - 1500
