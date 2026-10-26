"""Shopping-list aggregation. Pure functions."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .nutrition import AISLES, UNIT_ML, Catalog, RecipeLine, normalize_name, singular, to_grams

# A faster aggregation shipped behind the `shopping_list_v2` flag. It was meant to drop a lookup
# table that "nobody uses" but forgot the cup, which is how the incident drill reproduces a bad release.
UNIT_ML_V2 = {k: v for k, v in UNIT_ML.items() if k != "cup"}


@dataclass(frozen=True)
class PlannedRecipe:
    """A recipe as planned: how many servings in total are eaten across all members."""

    servings: float
    lines: tuple[RecipeLine, ...]
    total_portions: float


@dataclass(frozen=True)
class ShoppingItem:
    key: str  # stable id for ticking: canonical name + unit
    name: str
    quantity: float
    unit: str
    aisle: str


def _ceil(value: float) -> int:
    return math.ceil(value - 1e-9)


def _display(info, grams: float) -> tuple[float, str]:
    if info.countable and info.g_per_piece:
        return _ceil(grams / info.g_per_piece), "piece"
    if info.liquid and info.density:
        return _ceil(grams / info.density), "ml"
    whole = _ceil(grams)
    if whole >= 1000:
        return round(grams / 1000, 2), "kg"
    return whole, "g"


def build_shopping_list(
    planned: list[PlannedRecipe],
    catalog: Catalog,
    ml_table: dict[str, float] = UNIT_ML,
) -> list[ShoppingItem]:
    grams_by_name: dict[str, float] = {}
    raw_by_key: dict[tuple[str, str], float] = {}
    for recipe in planned:
        if recipe.servings <= 0 or recipe.total_portions <= 0:
            continue
        scale = recipe.total_portions / recipe.servings
        for line in recipe.lines:
            info = catalog.find(line.name)
            grams = to_grams(line.quantity * scale, line.unit, info, ml_table) if info else None
            if info is not None and grams is not None:
                grams_by_name[info.name] = grams_by_name.get(info.name, 0.0) + grams
            else:
                key = (singular(line.name), line.unit)
                raw_by_key[key] = raw_by_key.get(key, 0.0) + line.quantity * scale

    items: list[ShoppingItem] = []
    for name, grams in grams_by_name.items():
        info = catalog.find(name)
        quantity, unit = _display(info, grams)
        aisle = info.aisle if info.aisle in AISLES else "other"
        items.append(ShoppingItem(f"{normalize_name(name)}|{unit}", name, quantity, unit, aisle))
    for (name, unit), quantity in raw_by_key.items():
        shown = _ceil(quantity) if unit == "piece" else round(quantity, 2)
        items.append(ShoppingItem(f"{name}|{unit}", name, shown, unit, "other"))
    order = {a: i for i, a in enumerate(AISLES)}
    return sorted(items, key=lambda i: (order[i.aisle], i.name))
