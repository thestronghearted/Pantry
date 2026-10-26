"""Idempotent startup seeding: bundled recipes and the optional synthetic-probe household."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Household, Member, PlanMeal, PlanPortion, Recipe, RecipeIngredient, User
from .security import hash_password, verify_password
from .seed.loader import load_recipes

log = logging.getLogger("pantry.seed")

PROBE_WEEK = date(2020, 1, 6)  # a Monday far in the past, never touched by real users
PROBE_MEALS = {
    "breakfast": "Overnight oats with blueberries",  # uses cups: exercises the v2 regression
    "lunch": "Egg fried rice",
    "dinner": "Chickpea and spinach curry",
}


def seed_recipes(session: Session) -> int:
    existing = set(session.scalars(select(Recipe.title).where(Recipe.household_id.is_(None))))
    added = 0
    for r in load_recipes():
        if r["title"] in existing:
            continue
        session.add(
            Recipe(
                household_id=None,
                title=r["title"],
                servings=r["servings"],
                prep_minutes=r["prep"],
                cook_minutes=r["cook"],
                difficulty=r["difficulty"],
                meal_types=r["meal_types"],
                steps=r["steps"],
                ingredients=[
                    RecipeIngredient(position=i, name=n, quantity=q, unit=u) for i, (n, q, u) in enumerate(r["ingredients"])
                ],
            )
        )
        added += 1
    session.commit()
    return added


def ensure_probe(factory: sessionmaker[Session], settings: Settings) -> None:
    """Create (or refresh) the household used by the responder's synthetic probe. Needs PROBE_* env vars."""
    if not (settings.probe_email and settings.probe_password):
        return
    with factory() as s:
        email = settings.probe_email.lower()
        user = s.scalar(select(User).where(User.email == email))
        if user is None:
            household = Household(name="Synthetic probe")
            s.add(household)
            s.flush()
            user = User(household_id=household.id, email=email, password_hash=hash_password(settings.probe_password))
            s.add(user)
            member = Member(
                household_id=household.id, name="Probe", sex="female", age=35, height_cm=165, weight_kg=65,
                activity="light", goal="maintain",
            )
            s.add(member)
            s.flush()
            for offset, (meal, title) in enumerate(PROBE_MEALS.items()):
                recipe = s.scalar(select(Recipe).where(Recipe.household_id.is_(None), Recipe.title == title))
                if recipe is None:
                    continue
                pm = PlanMeal(
                    household_id=household.id, week_start=PROBE_WEEK, day=PROBE_WEEK + timedelta(days=0), meal=meal,
                    recipe_id=recipe.id,
                )
                pm.portions.append(PlanPortion(member_id=member.id, servings=1.0))
                s.add(pm)
            log.info("probe household created")
        elif not verify_password(settings.probe_password, user.password_hash):
            user.password_hash = hash_password(settings.probe_password)
        s.commit()
