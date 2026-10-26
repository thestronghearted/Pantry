from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.domain.nutrition import RecipeLine, recipe_macros
from app.domain.planner import DIFFICULTY_RANK, PlanMember, PlanRecipe, generate_week
from app.seed.loader import load_catalog, load_recipes

MONDAY = date(2026, 11, 2)


@pytest.fixture(scope="module")
def recipes():
    cat = load_catalog()
    out = []
    for i, r in enumerate(load_recipes(), start=1):
        m = recipe_macros([RecipeLine(*l) for l in r["ingredients"]], r["servings"], cat).per_serving
        out.append(PlanRecipe(i, r["title"], r["difficulty"], tuple(r["meal_types"]), r["prep"] + r["cook"], m.kcal))
    return out


@pytest.fixture
def family():
    return [PlanMember(1, 1900), PlanMember(2, 2400), PlanMember(3, 1500)]


def easy_week(recipes, members, **overrides):
    kwargs = dict(week_start=MONDAY, members=members, recipes=recipes, max_difficulty="easy", max_minutes_per_day=120)
    kwargs.update(overrides)
    return generate_week(**kwargs)


def test_default_limits_fill_a_whole_week(recipes, family):
    week = easy_week(recipes, family)
    assert len(week) == 7
    assert [d.day for d in week] == [MONDAY + timedelta(days=i) for i in range(7)]
    for d in week:
        assert [s.meal for s in d.slots] == ["breakfast", "lunch", "dinner"]


def test_only_allowed_difficulty_and_time_respected(recipes, family):
    by_id = {r.id: r for r in recipes}
    week = easy_week(recipes, family, max_minutes_per_day=75)
    assert week
    for d in week:
        assert d.cooking_minutes <= 75
        for s in d.slots:
            assert DIFFICULTY_RANK[by_id[s.recipe_id].difficulty] == 0


def test_portions_are_quarter_steps_within_bounds(recipes, family):
    for d in easy_week(recipes, family):
        for s in d.slots:
            for p in s.portions.values():
                assert 0.5 <= p <= 2.0
                assert (p * 4) % 1 == 0


def test_each_member_within_ten_percent_on_most_days(recipes, family):
    week = easy_week(recipes, family)
    assert sum(1 for d in week if not d.off_target) >= 6


def test_portions_differ_per_member(recipes, family):
    dinner = easy_week(recipes, family)[0].slots[2].portions
    assert dinner[2] >= dinner[3]  # the 2400 kcal member eats at least as much as the 1500 kcal one


def test_deterministic_for_same_seed_and_different_for_other(recipes, family):
    kwargs = dict(max_difficulty="medium")
    pick = lambda w: [[s.recipe_id for s in d.slots] for d in w]
    a = pick(easy_week(recipes, family, seed=1, **kwargs))
    b = pick(easy_week(recipes, family, seed=1, **kwargs))
    c = pick(easy_week(recipes, family, seed=2, **kwargs))
    assert a == b
    assert a != c


def test_no_repeat_window_avoids_recent_recipes(recipes, family):
    week = easy_week(recipes, family, no_repeat_days=2)
    for i in range(1, len(week)):
        prev = {s.recipe_id for s in week[i - 1].slots}
        assert not prev & {s.recipe_id for s in week[i].slots}


def test_skipped_meal_gives_zero_portion(recipes):
    members = [PlanMember(1, 2000), PlanMember(2, 1800, eats=("breakfast", "dinner"))]
    for d in easy_week(recipes, members):
        lunch = next(s for s in d.slots if s.meal == "lunch")
        assert lunch.portions[2] == 0.0
        assert lunch.portions[1] > 0


def test_incomplete_and_archived_recipes_are_never_planned(recipes, family):
    broken = [replace(r, complete=False) if r.id % 2 else replace(r, archived=True) for r in recipes]
    assert generate_week(week_start=MONDAY, members=family, recipes=broken) == []


def test_impossible_time_limit_returns_nothing_without_crashing(recipes, family):
    assert easy_week(recipes, family, max_minutes_per_day=1) == []


def test_unreachable_target_flags_off_target(recipes):
    week = easy_week(recipes, [PlanMember(1, 6000)])
    assert week and all(d.off_target for d in week)
