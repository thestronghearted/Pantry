import pytest

from app.domain.portions import MAX_PORTION, MIN_PORTION, best_day_portions, meal_targets, nearest_portion


def test_meal_split_sums_to_daily_target():
    t = meal_targets(2000, ["breakfast", "lunch", "dinner"])
    assert t == {"breakfast": 500, "lunch": 700, "dinner": 800}


def test_split_renormalises_when_meal_skipped():
    t = meal_targets(2000, ["lunch", "dinner"])
    assert sum(t.values()) == pytest.approx(2000)
    assert t["dinner"] > t["lunch"]


def test_nearest_portion_uses_quarter_steps_and_bounds():
    assert nearest_portion(500, 500) == 1.0
    assert nearest_portion(560, 500) == 1.0  # 1.12 -> 1.0 (closer than 1.25)
    assert nearest_portion(100, 500) == MIN_PORTION
    assert nearest_portion(5000, 500) == MAX_PORTION
    assert (nearest_portion(640, 500) * 4) % 1 == 0


def test_best_day_portions_lands_near_daily_target():
    per_serving = {"breakfast": 350.0, "lunch": 450.0, "dinner": 550.0}
    targets = meal_targets(1800, list(per_serving))
    portions, error = best_day_portions(per_serving, targets, 1800)
    day = sum(portions[m] * per_serving[m] for m in per_serving)
    assert abs(day - 1800) / 1800 == pytest.approx(error)
    assert error < 0.05
    assert all(MIN_PORTION <= p <= MAX_PORTION for p in portions.values())


def test_infeasible_day_reports_large_error():
    portions, error = best_day_portions({"dinner": 900.0}, {"dinner": 300.0}, 300)
    assert portions["dinner"] == MIN_PORTION
    assert error > 0.10
