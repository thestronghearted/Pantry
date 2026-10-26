"""Splitting a daily calorie target across meals and sizing portions. Pure functions."""
from __future__ import annotations

from itertools import product

MEALS = ("breakfast", "lunch", "dinner")
MEAL_SPLIT = {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.40}
STEP = 0.25
MIN_PORTION = 0.5
MAX_PORTION = 2.0
PORTION_OPTIONS = tuple(MIN_PORTION + i * STEP for i in range(int((MAX_PORTION - MIN_PORTION) / STEP) + 1))
TOLERANCE = 0.10


def meal_targets(daily_kcal: float, meals_eaten: list[str]) -> dict[str, float]:
    """Split a daily target over the meals eaten, renormalising the 25/35/40 split."""
    total = sum(MEAL_SPLIT[m] for m in meals_eaten)
    if total == 0:
        return {}
    return {m: daily_kcal * MEAL_SPLIT[m] / total for m in meals_eaten}


def nearest_portion(target_kcal: float, kcal_per_serving: float) -> float:
    """Portion (0.25 steps, 0.5-2.0) whose calories are closest to the target."""
    if kcal_per_serving <= 0:
        return MIN_PORTION
    return min(PORTION_OPTIONS, key=lambda p: (abs(p * kcal_per_serving - target_kcal), p))


def best_day_portions(
    kcal_per_serving: dict[str, float],
    meal_target: dict[str, float],
    daily_target: float,
) -> tuple[dict[str, float], float]:
    """Choose portions for the meals a member eats so the day total is as close to target as possible.

    Brute force over at most 7**3 combinations. Ties prefer portions near the per-meal targets.
    Returns (portion by meal, relative day error).
    """
    meals = list(kcal_per_serving)
    if not meals:
        return {}, 0.0
    best: tuple[float, float, tuple[float, ...]] | None = None
    for combo in product(PORTION_OPTIONS, repeat=len(meals)):
        day = sum(p * kcal_per_serving[m] for p, m in zip(combo, meals))
        day_err = abs(day - daily_target)
        meal_err = sum(abs(p * kcal_per_serving[m] - meal_target[m]) for p, m in zip(combo, meals))
        key = (round(day_err, 6), meal_err, combo)
        if best is None or key < best:
            best = key  # type: ignore[assignment]
    assert best is not None
    portions = dict(zip(meals, best[2]))
    return portions, best[0] / daily_target if daily_target else 0.0
