"""Weekly plan generator for a family. Pure functions, deterministic for a given seed."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import product

from .portions import MEALS, TOLERANCE, best_day_portions, meal_targets

DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}
TOP_CANDIDATES = 4


@dataclass(frozen=True)
class PlanRecipe:
    id: int
    title: str
    difficulty: str
    meal_types: tuple[str, ...]
    total_minutes: int
    kcal_per_serving: float
    complete: bool = True
    archived: bool = False


@dataclass(frozen=True)
class PlanMember:
    id: int
    daily_kcal: float
    eats: tuple[str, ...] = MEALS  # meals this person eats


@dataclass
class SlotPlan:
    meal: str
    recipe_id: int
    portions: dict[int, float]  # member id -> servings


@dataclass
class DayPlan:
    day: date
    slots: list[SlotPlan] = field(default_factory=list)
    cooking_minutes: int = 0
    off_target: bool = False
    member_error: dict[int, float] = field(default_factory=dict)


def eligible(recipes: list[PlanRecipe], meal: str, max_difficulty: str, max_minutes: int) -> list[PlanRecipe]:
    cap = DIFFICULTY_RANK[max_difficulty]
    return [
        r
        for r in recipes
        if r.complete
        and not r.archived
        and meal in r.meal_types
        and DIFFICULTY_RANK[r.difficulty] <= cap
        and r.total_minutes <= max_minutes
        and r.kcal_per_serving > 0
    ]


def _member_fit(member: PlanMember, combo: dict[str, PlanRecipe]) -> tuple[dict[str, float], float]:
    eaten = [m for m in member.eats if m in combo]
    if not eaten:
        return {}, 0.0
    targets = meal_targets(member.daily_kcal, eaten)
    return best_day_portions({m: combo[m].kcal_per_serving for m in eaten}, targets, member.daily_kcal)


def _plan_day(
    day: date,
    members: list[PlanMember],
    meals: list[str],
    pools: dict[str, list[PlanRecipe]],
    recent: set[int],
    max_minutes: int,
    rng: random.Random,
) -> DayPlan | None:
    """Pick the recipe combination for one day that best fits every member."""
    options: list[list[PlanRecipe]] = []
    for meal in meals:
        pool = pools[meal]
        fresh = [r for r in pool if r.id not in recent] or pool  # relax the repeat window if it empties the pool
        # Rank by closeness to the family's average meal target, with seeded jitter for variety.
        avg_target = sum(
            meal_targets(m.daily_kcal, [x for x in m.eats if x in meals]).get(meal, 0.0) for m in members
        ) / max(1, len(members))
        ranked = sorted(fresh, key=lambda r: abs(r.kcal_per_serving - avg_target) * (0.9 + 0.2 * rng.random()))
        options.append(ranked[:TOP_CANDIDATES])
    if any(not o for o in options):
        return None

    best: tuple[float, float, dict[str, PlanRecipe]] | None = None
    for combo_list in product(*options):
        if len({r.id for r in combo_list}) < len(combo_list):
            continue  # no duplicate recipe within a day
        minutes = sum(r.total_minutes for r in combo_list)
        if minutes > max_minutes:
            continue
        combo = dict(zip(meals, combo_list))
        error = sum(_member_fit(m, combo)[1] for m in members) / max(1, len(members))
        key = (round(error, 6), rng.random())
        if best is None or key < best[:2]:
            best = (key[0], key[1], combo)
    if best is None:
        return None

    combo = best[2]
    plan = DayPlan(day=day, cooking_minutes=sum(r.total_minutes for r in combo.values()))
    errors: dict[int, float] = {}
    per_member = {m.id: _member_fit(m, combo) for m in members}
    for meal in meals:
        portions = {}
        for m in members:
            chosen, _ = per_member[m.id]
            portions[m.id] = chosen.get(meal, 0.0)
        plan.slots.append(SlotPlan(meal=meal, recipe_id=combo[meal].id, portions=portions))
    for m in members:
        errors[m.id] = per_member[m.id][1]
    plan.member_error = errors
    plan.off_target = any(e > TOLERANCE + 1e-9 for e in errors.values())
    return plan


def generate_week(
    *,
    week_start: date,
    members: list[PlanMember],
    recipes: list[PlanRecipe],
    meals: list[str] | None = None,
    max_difficulty: str = "medium",
    max_minutes_per_day: int = 90,
    no_repeat_days: int = 3,
    seed: int = 0,
) -> list[DayPlan]:
    """Generate seven days. Days that cannot be filled are omitted from the result."""
    meals = [m for m in (meals or list(MEALS)) if m in MEALS]
    if not meals or not members:
        return []
    pools = {meal: eligible(recipes, meal, max_difficulty, max_minutes_per_day) for meal in meals}
    days: list[DayPlan] = []
    history: list[set[int]] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        rng = random.Random(f"{seed}:{day.isoformat()}")
        recent: set[int] = set().union(*history[-no_repeat_days:]) if no_repeat_days and history else set()
        plan = _plan_day(day, members, meals, pools, recent, max_minutes_per_day, rng)
        if plan is None:
            history.append(set())
            continue
        days.append(plan)
        history.append({s.recipe_id for s in plan.slots})
    return days
