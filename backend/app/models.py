"""SQLAlchemy models. Portable types only (no Postgres-specific columns)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Household(Base):
    __tablename__ = "households"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Member(Base):
    __tablename__ = "members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    sex: Mapped[str] = mapped_column(String(10))
    age: Mapped[int] = mapped_column(Integer)
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    activity: Mapped[str] = mapped_column(String(20))
    goal: Mapped[str] = mapped_column(String(10))
    kg_per_week: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_kcal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Ingredient(Base):
    """A household's custom ingredient, nutrition per 100 g. The bundled table lives in seed/nutrition.json."""

    __tablename__ = "ingredients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    density: Mapped[float | None] = mapped_column(Float, nullable=True)
    g_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)
    aisle: Mapped[str] = mapped_column(String(20), default="other")
    countable: Mapped[bool] = mapped_column(Boolean, default=False)
    liquid: Mapped[bool] = mapped_column(Boolean, default=False)


class Recipe(Base):
    """household_id NULL = global read-only seed recipe."""

    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int | None] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(120))
    servings: Mapped[float] = mapped_column(Float)
    prep_minutes: Mapped[int] = mapped_column(Integer)
    cook_minutes: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(10))
    meal_types: Mapped[list] = mapped_column(JSON, default=list)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    override_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    override_protein: Mapped[float | None] = mapped_column(Float, nullable=True)
    override_carbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    override_fat: Mapped[float | None] = mapped_column(Float, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    source_recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeIngredient.position"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")


class PlanMeal(Base):
    __tablename__ = "plan_meals"
    __table_args__ = (UniqueConstraint("household_id", "day", "meal", name="uq_plan_slot"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    day: Mapped[date] = mapped_column(Date)
    meal: Mapped[str] = mapped_column(String(10))
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"))  # NO ACTION: a planned recipe cannot be deleted

    portions: Mapped[list["PlanPortion"]] = relationship(back_populates="meal", cascade="all, delete-orphan")


class PlanPortion(Base):
    __tablename__ = "plan_portions"
    __table_args__ = (UniqueConstraint("plan_meal_id", "member_id", name="uq_portion"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_meal_id: Mapped[int] = mapped_column(ForeignKey("plan_meals.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    servings: Mapped[float] = mapped_column(Float, default=0.0)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)

    meal: Mapped[PlanMeal] = relationship(back_populates="portions")


class ShoppingCheck(Base):
    __tablename__ = "shopping_checks"
    __table_args__ = (UniqueConstraint("household_id", "week_start", "item_key", name="uq_check"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date)
    item_key: Mapped[str] = mapped_column(String(160))


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
