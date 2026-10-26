"""FastAPI dependencies: database session, authenticated household, ingredient catalog."""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.nutrition import Catalog, IngredientInfo
from .models import Ingredient, User


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def get_household_id(user: User = Depends(get_user)) -> int:
    return user.household_id


def to_info(row: Ingredient) -> IngredientInfo:
    return IngredientInfo(
        name=row.name,
        kcal=row.kcal,
        protein=row.protein,
        carbs=row.carbs,
        fat=row.fat,
        density=row.density,
        g_per_piece=row.g_per_piece,
        aisle=row.aisle,
        countable=row.countable,
        liquid=row.liquid,
        aliases=tuple(row.aliases or ()),
    )


def build_catalog(db: Session, household_id: int, global_items: list[IngredientInfo]) -> Catalog:
    custom = [to_info(r) for r in db.scalars(select(Ingredient).where(Ingredient.household_id == household_id))]
    return Catalog(custom + global_items)  # household entries win on name clashes


def get_catalog(request: Request, db: Session = Depends(get_db), household_id: int = Depends(get_household_id)) -> Catalog:
    return build_catalog(db, household_id, request.app.state.global_ingredients)
