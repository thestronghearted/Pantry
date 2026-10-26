"""Load the bundled nutrition table and seed recipes from JSON."""
from __future__ import annotations

import json
from pathlib import Path

from app.domain.nutrition import Catalog, IngredientInfo

SEED_DIR = Path(__file__).parent


def load_ingredients() -> list[IngredientInfo]:
    data = json.loads((SEED_DIR / "nutrition.json").read_text(encoding="utf-8"))["ingredients"]
    return [
        IngredientInfo(
            name=i["name"],
            kcal=i["kcal"],
            protein=i["protein"],
            carbs=i["carbs"],
            fat=i["fat"],
            density=i.get("density"),
            g_per_piece=i.get("g_per_piece"),
            aisle=i.get("aisle", "other"),
            countable=i.get("countable", False),
            liquid=i.get("liquid", False),
            aliases=tuple(i.get("aliases", [])),
        )
        for i in data
    ]


def load_recipes() -> list[dict]:
    return json.loads((SEED_DIR / "recipes.json").read_text(encoding="utf-8"))


def load_catalog() -> Catalog:
    return Catalog(load_ingredients())
