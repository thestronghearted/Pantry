from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..deps import get_catalog, get_db, get_household_id
from ..domain.nutrition import Catalog
from ..domain.planner import PlanMember, generate_week
from ..domain.portions import MEALS, best_day_portions, meal_targets
from ..domain.targets import TargetError
from ..metrics import PLAN_DAYS_OFF_TARGET, journey
from ..models import Member, PlanMeal, PlanPortion
from ..schemas import GenerateIn, Meal, PortionIn, SlotIn
from ..services import (
    MEAL_ORDER,
    get_visible_recipe,
    macros_for,
    member_targets,
    monday_of,
    plan_recipe_pool,
    plan_view,
    require_monday,
)

router = APIRouter(prefix="/api/plan", tags=["plan"])


def _members(db: Session, household_id: int) -> list[Member]:
    return list(db.scalars(select(Member).where(Member.household_id == household_id).order_by(Member.id)))


@router.get("")
def get_plan(
    week: date,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    return plan_view(db, household_id, require_monday(week), catalog)


@router.post("/generate")
def generate(
    body: GenerateIn,
    request: Request,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    synthetic = request.headers.get("x-synthetic") == "1"
    with journey("generate_plan", synthetic=synthetic, household_id=household_id):
        week = require_monday(body.week_start)
        members = _members(db, household_id)
        if not members:
            raise HTTPException(status_code=422, detail="Add at least one family member before generating a plan.")
        meals = [m for m in MEALS if m in body.meals]
        eats = body.eats or {}
        plan_members = []
        for m in members:
            try:
                kcal = member_targets(m).kcal
            except TargetError as exc:
                raise HTTPException(status_code=422, detail=f"{m.name}: {exc}") from exc
            eaten = tuple(x for x in meals if x in eats.get(m.id, meals))
            plan_members.append(PlanMember(m.id, kcal, eaten))

        days = generate_week(
            week_start=week,
            members=plan_members,
            recipes=plan_recipe_pool(db, household_id, catalog),
            meals=meals,
            max_difficulty=body.max_difficulty,
            max_minutes_per_day=body.max_minutes_per_day,
            no_repeat_days=body.no_repeat_days,
            seed=body.seed,
        )
        if not days:
            raise HTTPException(
                status_code=422,
                detail="No recipes fit those limits. Try allowing harder recipes or more cooking time per day.",
            )

        db.execute(delete(PlanPortion).where(PlanPortion.plan_meal_id.in_(
            select(PlanMeal.id).where(PlanMeal.household_id == household_id, PlanMeal.week_start == week))))
        db.execute(delete(PlanMeal).where(PlanMeal.household_id == household_id, PlanMeal.week_start == week))
        for day in days:
            for slot in day.slots:
                pm = PlanMeal(household_id=household_id, week_start=week, day=day.day, meal=slot.meal, recipe_id=slot.recipe_id)
                for member in plan_members:
                    servings = slot.portions.get(member.id, 0.0)
                    skipped = slot.meal not in member.eats
                    pm.portions.append(PlanPortion(member_id=member.id, servings=servings, skipped=skipped))
                db.add(pm)
        db.commit()
        PLAN_DAYS_OFF_TARGET.inc(sum(1 for d in days if d.off_target))
    return plan_view(db, household_id, week, catalog)


def _slot(db: Session, household_id: int, day: date, meal: str) -> PlanMeal | None:
    return db.scalar(
        select(PlanMeal)
        .where(PlanMeal.household_id == household_id, PlanMeal.day == day, PlanMeal.meal == meal)
        .options(selectinload(PlanMeal.portions))
    )


def _rebalance_day(db: Session, household_id: int, day: date, catalog: Catalog) -> None:
    """Recompute portions for everyone who has not skipped, after the day's recipes changed."""
    members = {m.id: m for m in _members(db, household_id)}
    slots = list(
        db.scalars(
            select(PlanMeal)
            .where(PlanMeal.household_id == household_id, PlanMeal.day == day)
            .options(selectinload(PlanMeal.portions))
        )
    )
    kcal = {}
    for s in slots:
        per_serving = macros_for(get_visible_recipe(db, s.recipe_id, household_id), catalog).per_serving
        kcal[s.meal] = per_serving.kcal if per_serving else 0.0
    for member in members.values():
        eaten = [s for s in slots if any(p.member_id == member.id and not p.skipped for p in s.portions)]
        if not eaten:
            continue
        names = [s.meal for s in eaten]
        daily = member_targets(member).kcal
        chosen, _ = best_day_portions({n: kcal[n] for n in names}, meal_targets(daily, names), daily)
        for s in eaten:
            for p in s.portions:
                if p.member_id == member.id:
                    p.servings = chosen[s.meal]


@router.put("/{day}/{meal}")
def swap_slot(
    day: date,
    meal: Meal,
    body: SlotIn,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    recipe = get_visible_recipe(db, body.recipe_id, household_id)
    if recipe.archived or not macros_for(recipe, catalog).complete:
        raise HTTPException(status_code=422, detail="That recipe is archived or has incomplete nutrition data.")
    slot = _slot(db, household_id, day, meal)
    if slot is None:
        slot = PlanMeal(household_id=household_id, week_start=monday_of(day), day=day, meal=meal, recipe_id=recipe.id)
        slot.portions = [PlanPortion(member_id=m.id, servings=1.0, skipped=False) for m in _members(db, household_id)]
        db.add(slot)
    else:
        slot.recipe_id = recipe.id
    db.flush()
    _rebalance_day(db, household_id, day, catalog)
    db.commit()
    return plan_view(db, household_id, monday_of(day), catalog)


@router.put("/{day}/{meal}/portions")
def set_portion(
    day: date,
    meal: Meal,
    body: PortionIn,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    slot = _slot(db, household_id, day, meal)
    if slot is None:
        raise HTTPException(status_code=404, detail="Nothing planned for that meal")
    portion = next((p for p in slot.portions if p.member_id == body.member_id), None)
    if portion is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if body.skipped is True or body.servings == 0:
        portion.skipped, portion.servings = True, 0.0
    elif body.servings is not None:
        portion.skipped, portion.servings = False, body.servings
    elif body.skipped is False:
        portion.skipped = False
        portion.servings = portion.servings or 1.0
    db.commit()
    return plan_view(db, household_id, monday_of(day), catalog)


@router.delete("/{day}/{meal}")
def clear_slot(
    day: date,
    meal: Meal,
    db: Session = Depends(get_db),
    household_id: int = Depends(get_household_id),
    catalog: Catalog = Depends(get_catalog),
):
    slot = _slot(db, household_id, day, meal)
    if slot is None:
        raise HTTPException(status_code=404, detail="Nothing planned for that meal")
    db.delete(slot)
    db.commit()
    return plan_view(db, household_id, monday_of(day), catalog)
