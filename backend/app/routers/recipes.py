from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..deps import get_catalog, get_db, get_household_id, to_info
from ..domain.nutrition import Catalog
from ..models import Ingredient, PlanMeal, Recipe, RecipeIngredient
from ..schemas import IngredientIn, RecipeIn
from ..services import get_visible_recipe, recipe_view, visible_recipe_query

router = APIRouter(prefix="/api", tags=["recipes"])

DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


def _apply(recipe: Recipe, body: RecipeIn) -> None:
    recipe.title = body.title
    recipe.servings = body.servings
    recipe.prep_minutes = body.prep_minutes
    recipe.cook_minutes = body.cook_minutes
    recipe.difficulty = body.difficulty
    recipe.meal_types = list(body.meal_types)
    recipe.steps = list(body.steps)
    o = body.macro_override
    recipe.override_kcal = o.kcal if o else None
    recipe.override_protein = o.protein if o else None
    recipe.override_carbs = o.carbs if o else None
    recipe.override_fat = o.fat if o else None
    recipe.ingredients = [
        RecipeIngredient(position=i, name=line.name, quantity=line.quantity, unit=line.unit)
        for i, line in enumerate(body.ingredients)
    ]


def _own(db: Session, recipe_id: int, household_id: int) -> Recipe:
    recipe = get_visible_recipe(db, recipe_id, household_id)
    if recipe.household_id is None:
        raise HTTPException(status_code=403, detail="Bundled recipes are read-only. Copy it to your recipes first.")
    return recipe


@router.get("/ingredients")
def search_ingredients(q: str = "", catalog: Catalog = Depends(get_catalog), household_id: int = Depends(get_household_id)):
    return [
        {
            "name": i.name,
            "kcal": i.kcal,
            "protein": i.protein,
            "carbs": i.carbs,
            "fat": i.fat,
            "aisle": i.aisle,
            "units": _units_for(i),
        }
        for i in catalog.search(q, limit=12)
    ]


def _units_for(info) -> list[str]:
    units = ["g", "kg"]
    if info.density:
        units += ["ml", "l", "tsp", "tbsp", "cup"]
    if info.g_per_piece:
        units.append("piece")
    return units


@router.post("/ingredients", status_code=201)
def create_ingredient(
    body: IngredientIn,
    request: Request,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
):
    name = body.name.lower()
    exists = db.scalar(
        select(func.count()).select_from(Ingredient).where(Ingredient.household_id == household_id, Ingredient.name == name)
    )
    if exists:
        raise HTTPException(status_code=409, detail="You already have a custom ingredient with that name")
    row = Ingredient(household_id=household_id, name=name, aliases=[], **body.model_dump(exclude={"name"}))
    row.countable = body.g_per_piece is not None
    db.add(row)
    db.commit()
    info = to_info(row)
    return {"name": info.name, "kcal": info.kcal, "units": _units_for(info)}


@router.get("/recipes")
def list_recipes(
    difficulty: str | None = Query(default=None, pattern="^(easy|medium|hard)$"),
    max_minutes: int | None = Query(default=None, ge=1),
    meal_type: str | None = Query(default=None, pattern="^(breakfast|lunch|dinner|snack)$"),
    q: str | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    stmt = visible_recipe_query(household_id).options(selectinload(Recipe.ingredients)).order_by(Recipe.title)
    if not include_archived:
        stmt = stmt.where(Recipe.archived.is_(False))
    if q:
        stmt = stmt.where(func.lower(Recipe.title).contains(q.lower()))
    out = []
    for r in db.scalars(stmt):
        if difficulty and DIFFICULTY_RANK[r.difficulty] > DIFFICULTY_RANK[difficulty]:
            continue
        if max_minutes and r.prep_minutes + r.cook_minutes > max_minutes:
            continue
        if meal_type and meal_type not in r.meal_types:
            continue
        out.append(recipe_view(r, catalog, household_id))
    return out


@router.post("/recipes", status_code=201)
def create_recipe(
    body: RecipeIn,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    recipe = Recipe(household_id=household_id)
    _apply(recipe, body)
    db.add(recipe)
    db.commit()
    return recipe_view(recipe, catalog, household_id)


@router.get("/recipes/{recipe_id}")
def get_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    return recipe_view(get_visible_recipe(db, recipe_id, household_id), catalog, household_id)


@router.put("/recipes/{recipe_id}")
def update_recipe(
    recipe_id: int,
    body: RecipeIn,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    recipe = _own(db, recipe_id, household_id)
    _apply(recipe, body)
    db.commit()
    return recipe_view(recipe, catalog, household_id)


@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, db: Session = Depends(get_db), household_id: int = Depends(get_household_id)):
    recipe = _own(db, recipe_id, household_id)
    planned = db.scalar(select(func.count()).select_from(PlanMeal).where(PlanMeal.recipe_id == recipe.id))
    if planned:
        recipe.archived = True  # still shown in existing plans, hidden from pickers
        db.commit()
        return {"deleted": False, "archived": True}
    db.delete(recipe)
    db.commit()
    return {"deleted": True, "archived": False}


@router.post("/recipes/{recipe_id}/copy", status_code=201)
def copy_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    source = get_visible_recipe(db, recipe_id, household_id)
    copy = Recipe(
        household_id=household_id,
        title=f"{source.title} (my copy)" if source.household_id is None else f"{source.title} (copy)",
        servings=source.servings,
        prep_minutes=source.prep_minutes,
        cook_minutes=source.cook_minutes,
        difficulty=source.difficulty,
        meal_types=list(source.meal_types),
        steps=list(source.steps),
        override_kcal=source.override_kcal,
        override_protein=source.override_protein,
        override_carbs=source.override_carbs,
        override_fat=source.override_fat,
        source_recipe_id=source.id,
        ingredients=[
            RecipeIngredient(position=i.position, name=i.name, quantity=i.quantity, unit=i.unit) for i in source.ingredients
        ],
    )
    db.add(copy)
    db.commit()
    return recipe_view(copy, catalog, household_id)
