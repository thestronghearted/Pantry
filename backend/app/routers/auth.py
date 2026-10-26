from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..deps import get_db, get_user
from ..models import (
    Household,
    Ingredient,
    Member,
    PlanMeal,
    PlanPortion,
    Recipe,
    RecipeIngredient,
    ShoppingCheck,
    User,
)
from ..schemas import DeleteHouseholdIn, LoginIn, SignupIn
from ..security import DUMMY_HASH, client_ip, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _limit(request: Request) -> None:
    s = request.app.state.settings
    request.app.state.limiter.check(client_ip(request, s.trust_proxy))


def _start_session(request: Request, user: User) -> None:
    request.session.clear()  # new session on every login
    request.session["user_id"] = user.id


@router.post("/signup", status_code=201)
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    _limit(request)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="That e-mail is already registered")
    household = Household(name=body.household_name)
    db.add(household)
    db.flush()
    user = User(household_id=household.id, email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    _start_session(request, user)
    return {"household": {"id": household.id, "name": household.name}, "email": user.email}


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _limit(request)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(status_code=401, detail="Incorrect e-mail or password")
    _start_session(request, user)
    household = db.get(Household, user.household_id)
    return {"household": {"id": household.id, "name": household.name}, "email": user.email}


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()


@router.get("/me")
def me(user: User = Depends(get_user), db: Session = Depends(get_db)):
    household = db.get(Household, user.household_id)
    return {"household": {"id": household.id, "name": household.name}, "email": user.email}


@router.delete("/household", status_code=204)
def delete_household(body: DeleteHouseholdIn, request: Request, user: User = Depends(get_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Password confirmation failed")
    hid = user.household_id
    meal_ids = select(PlanMeal.id).where(PlanMeal.household_id == hid)
    recipe_ids = select(Recipe.id).where(Recipe.household_id == hid)
    db.execute(delete(PlanPortion).where(PlanPortion.plan_meal_id.in_(meal_ids)))
    db.execute(delete(PlanMeal).where(PlanMeal.household_id == hid))
    db.execute(delete(ShoppingCheck).where(ShoppingCheck.household_id == hid))
    db.execute(update(Recipe).where(Recipe.source_recipe_id.in_(recipe_ids)).values(source_recipe_id=None))
    db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id.in_(recipe_ids)))
    db.execute(delete(Recipe).where(Recipe.household_id == hid))
    db.execute(delete(Ingredient).where(Ingredient.household_id == hid))
    db.execute(delete(Member).where(Member.household_id == hid))
    db.execute(delete(User).where(User.household_id == hid))
    db.execute(delete(Household).where(Household.id == hid))
    db.commit()
    request.session.clear()
