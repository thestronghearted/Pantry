"""Request/response models."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Sex = Literal["female", "male"]
Activity = Literal["sedentary", "light", "moderate", "active", "very_active"]
Goal = Literal["lose", "maintain", "custom"]
Difficulty = Literal["easy", "medium", "hard"]
Meal = Literal["breakfast", "lunch", "dinner"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
Unit = Literal["g", "kg", "ml", "l", "tsp", "tbsp", "cup", "piece"]
Aisle = Literal["produce", "dairy", "meat_fish", "pantry", "frozen", "other"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- auth
class SignupIn(Strict):
    household_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class DeleteHouseholdIn(Strict):
    password: str


# ---- members
class MemberIn(Strict):
    name: str = Field(min_length=1, max_length=60)
    sex: Sex
    age: int = Field(ge=1, le=110)
    height_cm: float = Field(gt=50, lt=260)
    weight_kg: float = Field(gt=10, lt=400)
    activity: Activity = "light"
    goal: Goal = "maintain"
    kg_per_week: float | None = None
    custom_kcal: int | None = None


# ---- ingredients / recipes
class IngredientIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    kcal: float = Field(ge=0, le=900)
    protein: float = Field(ge=0, le=100)
    carbs: float = Field(ge=0, le=100)
    fat: float = Field(ge=0, le=100)
    density: float | None = Field(default=None, gt=0, le=5)
    g_per_piece: float | None = Field(default=None, gt=0, le=5000)
    aisle: Aisle = "other"


class RecipeLineIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0, le=100000)
    unit: Unit


class MacroOverride(Strict):
    kcal: float = Field(ge=0, le=3000)
    protein: float = Field(ge=0, le=300)
    carbs: float = Field(ge=0, le=500)
    fat: float = Field(ge=0, le=300)


class RecipeIn(Strict):
    title: str = Field(min_length=1, max_length=120)
    servings: float = Field(gt=0, le=50)
    prep_minutes: int = Field(ge=0, le=1440)
    cook_minutes: int = Field(ge=0, le=1440)
    difficulty: Difficulty
    meal_types: list[MealType] = Field(min_length=1)
    ingredients: list[RecipeLineIn] = Field(min_length=1, max_length=60)
    steps: list[str] = Field(default_factory=list, max_length=40)
    macro_override: MacroOverride | None = None

    @field_validator("steps")
    @classmethod
    def _clean_steps(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()]


# ---- plan
class GenerateIn(Strict):
    week_start: date
    meals: list[Meal] = Field(default_factory=lambda: ["breakfast", "lunch", "dinner"], min_length=1)
    max_difficulty: Difficulty = "medium"
    max_minutes_per_day: int = Field(default=90, ge=10, le=600)
    no_repeat_days: int = Field(default=3, ge=0, le=7)
    seed: int = 0
    eats: dict[int, list[Meal]] | None = None  # member id -> meals eaten; default all


class SlotIn(Strict):
    recipe_id: int


class PortionIn(Strict):
    member_id: int
    servings: float | None = Field(default=None, ge=0, le=4)
    skipped: bool | None = None

    @field_validator("servings")
    @classmethod
    def _quarter_steps(cls, v: float | None) -> float | None:
        if v is not None and (v * 4) % 1 != 0:
            raise ValueError("servings must be a multiple of 0.25")
        return v


class CheckIn(Strict):
    week: date
    key: str = Field(min_length=1, max_length=160)
    checked: bool


class FlagIn(Strict):
    enabled: bool
