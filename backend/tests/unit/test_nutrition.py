import pytest

from app.domain.nutrition import Catalog, IngredientInfo, Macros, RecipeLine, recipe_macros, singular, to_grams
from app.seed.loader import load_catalog, load_ingredients, load_recipes


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_seed_table_has_at_least_sixty_ingredients_with_unique_names():
    items = load_ingredients()
    assert len(items) >= 60
    assert len({i.name for i in items}) == len(items)


def test_lookup_by_alias_case_and_plural(catalog):
    assert catalog.find("Eggs").name == "egg"
    assert catalog.find("  TOMATOES ").name == "tomato"
    assert catalog.find("skinless chicken breast").name == "chicken breast"
    assert catalog.find("dragon fruit") is None


def test_singular_handles_exceptions():
    assert singular("couscous") == "couscous"
    assert singular("potatoes") == "potato"
    assert singular("berries") == "berry"


def test_search_prefers_prefix_matches(catalog):
    names = [i.name for i in catalog.search("chick")]
    assert names[0] in {"chicken breast", "chicken thigh", "chickpeas"}
    assert catalog.search("") == []


def test_unit_conversion(catalog):
    milk = catalog.find("milk")
    assert to_grams(2, "kg", milk) == 2000
    assert to_grams(1, "cup", milk) == pytest.approx(236.588 * 1.03)
    assert to_grams(2, "piece", catalog.find("egg")) == 100
    assert to_grams(1, "piece", milk) is None  # no piece weight
    assert to_grams(1, "cup", catalog.find("chicken breast")) is None  # no density


def test_macros_per_serving_scale_by_servings():
    oats = IngredientInfo("oats", kcal=400, protein=10, carbs=60, fat=8)
    cat = Catalog([oats])
    res = recipe_macros([RecipeLine("oats", 100, "g")], servings=2, catalog=cat)
    assert res.complete
    assert res.per_serving.kcal == pytest.approx(200)
    assert res.per_serving.protein == pytest.approx(5)


def test_unknown_ingredient_marks_recipe_incomplete(catalog):
    res = recipe_macros([RecipeLine("unicorn meat", 100, "g"), RecipeLine("egg", 1, "piece")], 1, catalog)
    assert not res.complete
    assert res.per_serving is None
    assert res.missing == ("unicorn meat",)


def test_ingredient_without_density_cannot_use_volume(catalog):
    res = recipe_macros([RecipeLine("chicken breast", 1, "cup")], 1, catalog)
    assert not res.complete


def test_override_wins_and_is_complete(catalog):
    res = recipe_macros([RecipeLine("unicorn meat", 1, "g")], 1, catalog, override=Macros(500, 30, 40, 20))
    assert res.complete and res.per_serving.kcal == 500


def test_every_seed_recipe_is_complete_and_plausible(catalog):
    for r in load_recipes():
        res = recipe_macros([RecipeLine(*l) for l in r["ingredients"]], r["servings"], catalog)
        assert res.complete, (r["title"], res.missing)
        assert 150 <= res.per_serving.kcal <= 700, r["title"]


def test_seed_has_enough_easy_recipes_per_meal_type():
    recipes = load_recipes()
    for meal in ("breakfast", "lunch", "dinner"):
        easy = [r for r in recipes if r["difficulty"] == "easy" and meal in r["meal_types"]]
        assert len(easy) >= 6, meal
    assert len(recipes) >= 30
