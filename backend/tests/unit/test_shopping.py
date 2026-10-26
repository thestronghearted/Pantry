import pytest

from app.domain.nutrition import RecipeLine
from app.domain.shopping import UNIT_ML_V2, PlannedRecipe, build_shopping_list
from app.seed.loader import load_catalog


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def planned(lines, servings=2, portions=2):
    return PlannedRecipe(servings, tuple(RecipeLine(*l) for l in lines), portions)


def by_name(items):
    return {i.name: i for i in items}


def test_scales_by_portions_over_servings(catalog):
    items = build_shopping_list([planned([("chicken breast", 300, "g")], servings=2, portions=3)], catalog)
    assert by_name(items)["chicken breast"].quantity == 450


def test_duplicates_across_recipes_are_summed_and_units_merged(catalog):
    items = build_shopping_list(
        [planned([("plain flour", 200, "g")], 1, 1), planned([("flour", 1, "cup")], 1, 1)],
        catalog,
    )
    flour = by_name(items)["plain flour"]
    assert flour.unit == "g"
    assert flour.quantity == pytest.approx(200 + 236.588 * 0.53, abs=1)


def test_countable_items_round_up_to_whole_pieces(catalog):
    items = build_shopping_list([planned([("egg", 3, "piece")], servings=2, portions=3.5)], catalog)
    egg = by_name(items)["egg"]
    assert (egg.quantity, egg.unit) == (6, "piece")  # 5.25 -> 6


def test_liquids_shown_in_millilitres(catalog):
    items = build_shopping_list([planned([("milk", 1, "cup")], 1, 1)], catalog)
    milk = by_name(items)["semi-skimmed milk"]
    assert (milk.unit, milk.quantity) == ("ml", 237)  # 236.588 ml rounded up


def test_large_weights_shown_in_kilograms(catalog):
    items = build_shopping_list([planned([("brown rice", 1500, "g")], 1, 1)], catalog)
    rice = by_name(items)["brown rice"]
    assert (rice.quantity, rice.unit) == (1.5, "kg")


def test_aisle_grouping_and_order(catalog):
    items = build_shopping_list(
        [planned([("pasta", 100, "g"), ("tomato", 2, "piece"), ("milk", 1, "tbsp"), ("chicken breast", 100, "g")])], catalog
    )
    order = ["produce", "dairy", "meat_fish", "pantry", "frozen", "other"]
    aisles = [i.aisle for i in items]
    assert aisles == sorted(aisles, key=order.index)


def test_unknown_ingredient_kept_as_its_own_line(catalog):
    items = build_shopping_list([planned([("dragon fruit", 2, "piece")], 1, 1)], catalog)
    line = by_name(items)["dragon fruit"]
    assert (line.quantity, line.unit, line.aisle) == (2, "piece", "other")


def test_zero_portions_contribute_nothing(catalog):
    assert build_shopping_list([planned([("egg", 2, "piece")], 2, 0)], catalog) == []


def test_empty_plan_gives_empty_list(catalog):
    assert build_shopping_list([], catalog) == []


def test_item_keys_are_stable_and_unique(catalog):
    items = build_shopping_list([planned([("egg", 2, "piece"), ("onion", 1, "piece"), ("olive oil", 1, "tbsp")])], catalog)
    keys = [i.key for i in items]
    assert len(keys) == len(set(keys))
    assert "egg|piece" in keys


def test_v2_table_regresses_on_cups_only(catalog):
    with pytest.raises(KeyError):
        build_shopping_list([planned([("rolled oats", 1, "cup")])], catalog, UNIT_ML_V2)
    # grams and tablespoons still work, which is why the bug only hits some plans
    assert build_shopping_list([planned([("rolled oats", 50, "g"), ("honey", 1, "tbsp")])], catalog, UNIT_ML_V2)
