"""Ingredient catalog, unit conversion and recipe macros. Pure functions, no I/O."""
from __future__ import annotations

from dataclasses import dataclass, field

UNITS = ("g", "kg", "ml", "l", "tsp", "tbsp", "cup", "piece")
UNIT_G = {"g": 1.0, "kg": 1000.0}
UNIT_ML = {"ml": 1.0, "l": 1000.0, "tsp": 4.929, "tbsp": 14.787, "cup": 236.588}

AISLES = ("produce", "dairy", "meat_fish", "pantry", "frozen", "other")

_SINGULAR_EXCEPTIONS = {"hummus", "asparagus", "couscous", "molasses", "swiss", "citrus"}


@dataclass(frozen=True)
class IngredientInfo:
    """Nutrition per 100 g plus the data needed to convert units."""

    name: str
    kcal: float
    protein: float
    carbs: float
    fat: float
    density: float | None = None  # g per ml; needed for volume units
    g_per_piece: float | None = None  # needed for "piece"
    aisle: str = "other"
    countable: bool = False  # shopping list shows whole pieces
    liquid: bool = False  # shopping list shows millilitres
    aliases: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class Macros:
    kcal: float
    protein: float
    carbs: float
    fat: float

    def scaled(self, factor: float) -> "Macros":
        return Macros(self.kcal * factor, self.protein * factor, self.carbs * factor, self.fat * factor)

    def __add__(self, other: "Macros") -> "Macros":
        return Macros(
            self.kcal + other.kcal,
            self.protein + other.protein,
            self.carbs + other.carbs,
            self.fat + other.fat,
        )


ZERO = Macros(0.0, 0.0, 0.0, 0.0)


def normalize_name(name: str) -> str:
    """Lower-case, collapse whitespace."""
    return " ".join(name.lower().strip().split())


def singular(name: str) -> str:
    n = normalize_name(name)
    if n in _SINGULAR_EXCEPTIONS or n.endswith("ss"):
        return n
    if n.endswith("ies") and len(n) > 4:
        return n[:-3] + "y"
    if n.endswith("oes") and len(n) > 4:
        return n[:-2]
    if n.endswith("s") and len(n) > 3:
        return n[:-1]
    return n


class Catalog:
    """Lookup of ingredients by name or alias, tolerant of case and plurals."""

    def __init__(self, items: list[IngredientInfo]):
        self._by_key: dict[str, IngredientInfo] = {}
        for item in items:
            for raw in (item.name, *item.aliases):
                self._by_key.setdefault(normalize_name(raw), item)
        for item in items:
            for raw in (item.name, *item.aliases):
                self._by_key.setdefault(singular(raw), item)
        self.items = list(items)

    def find(self, name: str) -> IngredientInfo | None:
        return self._by_key.get(normalize_name(name)) or self._by_key.get(singular(name))

    def search(self, query: str, limit: int = 10) -> list[IngredientInfo]:
        q = normalize_name(query)
        if not q:
            return []
        starts, contains = [], []
        for item in self.items:
            names = [normalize_name(n) for n in (item.name, *item.aliases)]
            if any(n.startswith(q) for n in names):
                starts.append(item)
            elif any(q in n for n in names):
                contains.append(item)
        return (sorted(starts, key=lambda i: i.name) + sorted(contains, key=lambda i: i.name))[:limit]


def to_grams(quantity: float, unit: str, info: IngredientInfo, ml_table: dict[str, float] = UNIT_ML) -> float | None:
    """Convert a quantity to grams, or None if the ingredient lacks the data (density / piece weight)."""
    if unit in UNIT_G:
        return quantity * UNIT_G[unit]
    if unit == "piece":
        return quantity * info.g_per_piece if info.g_per_piece else None
    millilitres = quantity * ml_table[unit]  # KeyError for a unit the table does not know
    return millilitres * info.density if info.density else None


@dataclass(frozen=True)
class RecipeLine:
    name: str
    quantity: float
    unit: str


@dataclass(frozen=True)
class MacroResult:
    per_serving: Macros | None
    complete: bool
    missing: tuple[str, ...]


def recipe_macros(
    lines: list[RecipeLine],
    servings: float,
    catalog: Catalog,
    override: Macros | None = None,
) -> MacroResult:
    """Macros per serving. An override (per serving) wins; otherwise every line must be convertible."""
    if override is not None:
        return MacroResult(override, True, ())
    if servings <= 0:
        raise ValueError("servings must be positive")
    total = ZERO
    missing: list[str] = []
    for line in lines:
        info = catalog.find(line.name)
        grams = to_grams(line.quantity, line.unit, info) if info else None
        if info is None or grams is None:
            missing.append(line.name)
            continue
        factor = grams / 100.0
        total = total + Macros(info.kcal * factor, info.protein * factor, info.carbs * factor, info.fat * factor)
    if missing:
        return MacroResult(None, False, tuple(missing))
    return MacroResult(total.scaled(1.0 / servings), True, ())
