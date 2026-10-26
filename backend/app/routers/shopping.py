from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..deps import get_catalog, get_db, get_household_id
from ..domain.nutrition import UNIT_ML, Catalog, RecipeLine
from ..domain.shopping import UNIT_ML_V2, PlannedRecipe, build_shopping_list
from ..metrics import journey
from ..models import PlanMeal, ShoppingCheck
from ..schemas import CheckIn
from ..services import get_visible_recipe, require_monday

router = APIRouter(prefix="/api/shopping-list", tags=["shopping"])


@router.get("")
def shopping_list(
    week: date,
    request: Request,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    synthetic = request.headers.get("x-synthetic") == "1"
    with journey("shopping_list", synthetic=synthetic, household_id=household_id):
        week = require_monday(week)
        meals = list(
            db.scalars(
                select(PlanMeal)
                .where(PlanMeal.household_id == household_id, PlanMeal.week_start == week)
                .options(selectinload(PlanMeal.portions))
            )
        )
        planned = []
        for pm in meals:
            recipe = get_visible_recipe(db, pm.recipe_id, household_id)
            planned.append(
                PlannedRecipe(
                    servings=recipe.servings,
                    lines=tuple(RecipeLine(i.name, i.quantity, i.unit) for i in recipe.ingredients),
                    total_portions=sum(p.servings for p in pm.portions),
                )
            )
        table = UNIT_ML_V2 if request.app.state.flags.enabled("shopping_list_v2") else UNIT_ML
        items = build_shopping_list(planned, catalog, table)
        checked = set(
            db.scalars(
                select(ShoppingCheck.item_key).where(
                    ShoppingCheck.household_id == household_id, ShoppingCheck.week_start == week
                )
            )
        )
        return {
            "week_start": week.isoformat(),
            "items": [
                {
                    "key": i.key,
                    "name": i.name,
                    "quantity": i.quantity,
                    "unit": i.unit,
                    "aisle": i.aisle,
                    "checked": i.key in checked,
                }
                for i in items
            ],
        }


@router.put("/checks", status_code=204)
def set_check(body: CheckIn, db: Session = Depends(get_db), household_id: int = Depends(get_household_id)):
    week = require_monday(body.week)
    where = (
        ShoppingCheck.household_id == household_id,
        ShoppingCheck.week_start == week,
        ShoppingCheck.item_key == body.key,
    )
    existing = db.scalar(select(ShoppingCheck).where(*where))
    if body.checked and not existing:
        db.add(ShoppingCheck(household_id=household_id, week_start=week, item_key=body.key))
    elif not body.checked and existing:
        db.execute(delete(ShoppingCheck).where(*where))
    db.commit()
