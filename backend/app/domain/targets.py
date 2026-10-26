"""Daily calorie and macro targets (Mifflin-St Jeor). Pure functions."""
from __future__ import annotations

from dataclasses import dataclass

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
KCAL_PER_KG_FAT = 7700
FLOOR_KCAL = {"male": 1500, "female": 1200}
MIN_CUSTOM_KCAL = 800
MAX_CUSTOM_KCAL = 5000
MAX_LOSS_KG_PER_WEEK = 1.0
NOTICE = "Estimates only, not medical advice. Talk to a doctor before starting a weight-loss plan."


class TargetError(ValueError):
    """The inputs cannot produce a valid target."""


@dataclass(frozen=True)
class Targets:
    kcal: int
    protein_g: int
    carbs_g: int
    fat_g: int
    effective_kg_per_week: float
    adjusted: bool
    notice: str = NOTICE


def bmr(sex: str, age: int, height_cm: float, weight_kg: float) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if sex == "male" else -161)


def split_macros(kcal: float, weight_kg: float) -> tuple[int, int, int]:
    """Protein 1.8 g/kg capped at 35% kcal, fat 25% kcal, carbs the remainder (never negative)."""
    protein = min(1.8 * weight_kg, 0.35 * kcal / 4)
    fat = 0.25 * kcal / 9
    carbs = max(0.0, (kcal - 4 * protein - 9 * fat) / 4)
    return round(protein), round(carbs), round(fat)


def compute_targets(
    *,
    sex: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    activity: str,
    goal: str,
    kg_per_week: float | None = None,
    custom_kcal: int | None = None,
) -> Targets:
    if sex not in FLOOR_KCAL:
        raise TargetError("sex must be 'female' or 'male'")
    if goal == "custom":
        if custom_kcal is None or not MIN_CUSTOM_KCAL <= custom_kcal <= MAX_CUSTOM_KCAL:
            raise TargetError(f"custom kcal must be between {MIN_CUSTOM_KCAL} and {MAX_CUSTOM_KCAL}")
        p, c, f = split_macros(custom_kcal, weight_kg)
        return Targets(custom_kcal, p, c, f, 0.0, False)

    if age < 18:
        raise TargetError("Adult formulas do not apply under 18; use a custom calorie target.")
    if activity not in ACTIVITY_FACTORS:
        raise TargetError("unknown activity level")
    if goal not in ("lose", "maintain"):
        raise TargetError("goal must be lose, maintain or custom")

    tdee = bmr(sex, age, height_cm, weight_kg) * ACTIVITY_FACTORS[activity]
    if goal == "maintain":
        kcal = round(tdee)
        p, c, f = split_macros(kcal, weight_kg)
        return Targets(kcal, p, c, f, 0.0, False)

    if kg_per_week is None or not 0.1 <= kg_per_week <= MAX_LOSS_KG_PER_WEEK:
        raise TargetError("kg_per_week must be between 0.1 and 1.0")
    wanted = tdee - kg_per_week * KCAL_PER_KG_FAT / 7
    floor = FLOOR_KCAL[sex]
    kcal = round(max(wanted, floor))
    adjusted = wanted < floor
    effective = round(max(0.0, (tdee - kcal) * 7 / KCAL_PER_KG_FAT), 2)
    p, c, f = split_macros(kcal, weight_kg)
    return Targets(kcal, p, c, f, effective if adjusted else kg_per_week, adjusted)
