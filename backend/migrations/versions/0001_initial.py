"""initial schema

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

NOW = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", NOW, nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", NOW, nullable=False),
    )
    op.create_index("ix_users_household_id", "users", ["household_id"])
    op.create_table(
        "members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("sex", sa.String(10), nullable=False),
        sa.Column("age", sa.Integer, nullable=False),
        sa.Column("height_cm", sa.Float, nullable=False),
        sa.Column("weight_kg", sa.Float, nullable=False),
        sa.Column("activity", sa.String(20), nullable=False),
        sa.Column("goal", sa.String(10), nullable=False),
        sa.Column("kg_per_week", sa.Float),
        sa.Column("custom_kcal", sa.Integer),
        sa.Column("created_at", NOW, nullable=False),
    )
    op.create_index("ix_members_household_id", "members", ["household_id"])
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("aliases", sa.JSON, nullable=False),
        sa.Column("kcal", sa.Float, nullable=False),
        sa.Column("protein", sa.Float, nullable=False),
        sa.Column("carbs", sa.Float, nullable=False),
        sa.Column("fat", sa.Float, nullable=False),
        sa.Column("density", sa.Float),
        sa.Column("g_per_piece", sa.Float),
        sa.Column("aisle", sa.String(20), nullable=False),
        sa.Column("countable", sa.Boolean, nullable=False),
        sa.Column("liquid", sa.Boolean, nullable=False),
    )
    op.create_index("ix_ingredients_household_id", "ingredients", ["household_id"])
    op.create_index("ix_ingredients_name", "ingredients", ["name"])
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("servings", sa.Float, nullable=False),
        sa.Column("prep_minutes", sa.Integer, nullable=False),
        sa.Column("cook_minutes", sa.Integer, nullable=False),
        sa.Column("difficulty", sa.String(10), nullable=False),
        sa.Column("meal_types", sa.JSON, nullable=False),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("override_kcal", sa.Float),
        sa.Column("override_protein", sa.Float),
        sa.Column("override_carbs", sa.Float),
        sa.Column("override_fat", sa.Float),
        sa.Column("archived", sa.Boolean, nullable=False),
        sa.Column("source_recipe_id", sa.Integer, sa.ForeignKey("recipes.id", ondelete="SET NULL")),
        sa.Column("created_at", NOW, nullable=False),
    )
    op.create_index("ix_recipes_household_id", "recipes", ["household_id"])
    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
    )
    op.create_index("ix_recipe_ingredients_recipe_id", "recipe_ingredients", ["recipe_id"])
    op.create_table(
        "plan_meals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("meal", sa.String(10), nullable=False),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id"), nullable=False),
        sa.UniqueConstraint("household_id", "day", "meal", name="uq_plan_slot"),
    )
    op.create_index("ix_plan_meals_household_id", "plan_meals", ["household_id"])
    op.create_index("ix_plan_meals_week_start", "plan_meals", ["week_start"])
    op.create_table(
        "plan_portions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_meal_id", sa.Integer, sa.ForeignKey("plan_meals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_id", sa.Integer, sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("servings", sa.Float, nullable=False),
        sa.Column("skipped", sa.Boolean, nullable=False),
        sa.UniqueConstraint("plan_meal_id", "member_id", name="uq_portion"),
    )
    op.create_index("ix_plan_portions_plan_meal_id", "plan_portions", ["plan_meal_id"])
    op.create_table(
        "shopping_checks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("item_key", sa.String(160), nullable=False),
        sa.UniqueConstraint("household_id", "week_start", "item_key", name="uq_check"),
    )
    op.create_index("ix_shopping_checks_household_id", "shopping_checks", ["household_id"])
    op.create_table(
        "feature_flags",
        sa.Column("name", sa.String(60), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("updated_at", NOW, nullable=False),
    )


def downgrade() -> None:
    for table in (
        "feature_flags", "shopping_checks", "plan_portions", "plan_meals", "recipe_ingredients",
        "recipes", "ingredients", "members", "users", "households",
    ):
        op.drop_table(table)
