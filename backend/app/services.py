"""Glue between the database and the pure domain functions."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .domain.nutrition import Catalog, MacroResult, Macros, RecipeLine, recipe_macros
from .domain.planner import PlanRecipe
from .domain.portions import MEAL_SPLIT, TOLERANCE
from .domain.targets import Targets, TargetError, compute_targets
from .models import Member, PlanMeal, Recipe

MEAL_ORDER = {"breakfast": 0, "lunch": 1, "dinner": 2}


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def require_monday(day: date) -> date:
    if day.weekday() != 0:
        raise HTTPException(status_code=422, detail=f"{day.isoformat()} is not a Monday; weeks start on Monday.")
    return day


def member_targets(m: Member) -> Targets:
    return compute_targets(
        sex=m.sex,
        age=m.age,
        height_cm=m.height_cm,
        weight_kg=m.weight_kg,
        activity=m.activity,
        goal=m.goal,
        kg_per_week=m.kg_per_week,
        custom_kcal=m.custom_kcal,
    )


def validated_targets(payload) -> Targets:
    """Targets for a MemberIn payload; a bad combination becomes a 422."""
    try:
        return compute_targets(
            sex=payload.sex,
            age=payload.age,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            activity=payload.activity,
            goal=payload.goal,
            kg_per_week=payload.kg_per_week,
            custom_kcal=payload.custom_kcal,
        )
    except TargetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def member_view(m: Member) -> dict:
    view = {
        "id": m.id,
        "name": m.name,
        "sex": m.sex,
        "age": m.age,
        "height_cm": m.height_cm,
        "weight_kg": m.weight_kg,
        "activity": m.activity,
        "goal": m.goal,
        "kg_per_week": m.kg_per_week,
        "custom_kcal": m.custom_kcal,
    }
    try:
        view["targets"] = asdict(member_targets(m))
    except TargetError:
        view["targets"] = None
    return view


def macros_for(recipe: Recipe, catalog: Catalog) -> MacroResult:
    override = None
    if recipe.override_kcal is not None:
        override = Macros(
            recipe.override_kcal, recipe.override_protein or 0.0, recipe.override_carbs or 0.0, recipe.override_fat or 0.0
        )
    lines = [RecipeLine(i.name, i.quantity, i.unit) for i in recipe.ingredients]
    return recipe_macros(lines, recipe.servings, catalog, override)


def round_macros(m: Macros | None) -> dict | None:
    if m is None:
        return None
    return {"kcal": round(m.kcal), "protein": round(m.protein, 1), "carbs": round(m.carbs, 1), "fat": round(m.fat, 1)}


def recipe_view(recipe: Recipe, catalog: Catalog, household_id: int) -> dict:
    result = macros_for(recipe, catalog)
    return {
        "id": recipe.id,
        "title": recipe.title,
        "servings": recipe.servings,
        "prep_minutes": recipe.prep_minutes,
        "cook_minutes": recipe.cook_minutes,
        "total_minutes": recipe.prep_minutes + recipe.cook_minutes,
        "difficulty": recipe.difficulty,
        "meal_types": recipe.meal_types,
        "steps": recipe.steps,
        "ingredients": [{"name": i.name, "quantity": i.quantity, "unit": i.unit} for i in recipe.ingredients],
        "macros_per_serving": round_macros(result.per_serving),
        "has_override": recipe.override_kcal is not None,
        "complete": result.complete,
        "missing_nutrition": list(result.missing),
        "is_global": recipe.household_id is None,
        "archived": recipe.archived,
    }


def visible_recipe_query(household_id: int):
    return select(Recipe).where((Recipe.household_id.is_(None)) | (Recipe.household_id == household_id))


def get_visible_recipe(db: Session, recipe_id: int, household_id: int) -> Recipe:
    recipe = db.scalar(
        visible_recipe_query(household_id).where(Recipe.id == recipe_id).options(selectinload(Recipe.ingredients))
    )
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def plan_recipe_pool(db: Session, household_id: int, catalog: Catalog) -> list[PlanRecipe]:
    rows = db.scalars(
        visible_recipe_query(household_id).where(Recipe.archived.is_(False)).options(selectinload(Recipe.ingredients))
    )
    pool = []
    for r in rows:
        res = macros_for(r, catalog)
        pool.append(
            PlanRecipe(
                id=r.id,
                title=r.title,
                difficulty=r.difficulty,
                meal_types=tuple(r.meal_types),
                total_minutes=r.prep_minutes + r.cook_minutes,
                kcal_per_serving=res.per_serving.kcal if res.per_serving else 0.0,
                complete=res.complete,
                archived=r.archived,
            )
        )
    return pool


def plan_view(db: Session, household_id: int, week_start: date, catalog: Catalog) -> dict:
    members = list(db.scalars(select(Member).where(Member.household_id == household_id).order_by(Member.id)))
    targets: dict[int, Targets] = {}
    for m in members:
        try:
            targets[m.id] = member_targets(m)
        except TargetError:
            pass

    meals = list(
        db.scalars(
            select(PlanMeal)
            .where(PlanMeal.household_id == household_id, PlanMeal.week_start == week_start)
            .options(selectinload(PlanMeal.portions))
        )
    )
    recipe_ids = {pm.recipe_id for pm in meals}
    recipes = {
        r.id: r
        for r in db.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids)).options(selectinload(Recipe.ingredients)))
    } if recipe_ids else {}
    macros = {rid: macros_for(r, catalog).per_serving for rid, r in recipes.items()}

    by_day: dict[date, list[PlanMeal]] = {}
    for pm in meals:
        by_day.setdefault(pm.day, []).append(pm)

    days = []
    weekly_minutes = 0
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        slots, minutes = [], 0
        totals = {m.id: Macros(0, 0, 0, 0) for m in members}
        for pm in sorted(by_day.get(day, []), key=lambda x: MEAL_ORDER.get(x.meal, 9)):
            recipe, per_serving = recipes[pm.recipe_id], macros[pm.recipe_id]
            minutes += recipe.prep_minutes + recipe.cook_minutes
            portions = []
            for p in sorted(pm.portions, key=lambda x: x.member_id):
                kcal = p.servings * per_serving.kcal if per_serving else 0.0
                if per_serving and p.member_id in totals:
                    totals[p.member_id] = totals[p.member_id] + per_serving.scaled(p.servings)
                portions.append({"member_id": p.member_id, "servings": p.servings, "skipped": p.skipped, "kcal": round(kcal)})
            slots.append(
                {
                    "meal": pm.meal,
                    "recipe": {
                        "id": recipe.id,
                        "title": recipe.title,
                        "difficulty": recipe.difficulty,
                        "total_minutes": recipe.prep_minutes + recipe.cook_minutes,
                        "macros_per_serving": round_macros(per_serving),
                    },
                    "portions": portions,
                }
            )
        member_totals, off_target = [], False
        if slots:
            for m in members:
                t = targets.get(m.id)
                err = abs(totals[m.id].kcal - t.kcal) / t.kcal if t and t.kcal else None
                if err is not None and err > TOLERANCE + 1e-9:
                    off_target = True
                member_totals.append(
                    {
                        "member_id": m.id,
                        **(round_macros(totals[m.id]) or {}),
                        "target_kcal": t.kcal if t else None,
                        "error": round(err, 3) if err is not None else None,
                    }
                )
        weekly_minutes += minutes
        days.append(
            {
                "date": day.isoformat(),
                "slots": slots,
                "cooking_minutes": minutes,
                "totals": member_totals,
                "off_target": off_target,
            }
        )
    return {
        "week_start": week_start.isoformat(),
        "members": [
            {"id": m.id, "name": m.name, "target_kcal": targets[m.id].kcal if m.id in targets else None} for m in members
        ],
        "days": days,
        "weekly_cooking_minutes": weekly_minutes,
        "meal_split": MEAL_SPLIT,
    }
