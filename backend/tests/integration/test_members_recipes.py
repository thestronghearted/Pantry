import pytest

from .conftest import ADULT, CHILD, add_member, signup

LINE = {"name": "egg", "quantity": 2, "unit": "piece"}
BASE_RECIPE = {
    "title": "Plain eggs",
    "servings": 1,
    "prep_minutes": 2,
    "cook_minutes": 5,
    "difficulty": "easy",
    "meal_types": ["breakfast"],
    "ingredients": [LINE],
    "steps": ["Boil eggs."],
}


# ---- members
def test_member_gets_targets_with_notice(client):
    signup(client)
    m = add_member(client, **ADULT)
    t = m["targets"]
    assert 1500 <= t["kcal"] < 3500
    assert t["carbs_g"] > 0 and t["protein_g"] > 0
    assert "not medical advice" in t["notice"]


def test_child_must_use_custom_calories(client):
    signup(client)
    bad = dict(CHILD, goal="lose", kg_per_week=0.5, custom_kcal=None)
    r = client.post("/api/members", json=bad)
    assert r.status_code == 422 and "18" in r.json()["detail"]
    assert add_member(client, **CHILD)["targets"]["kcal"] == 1900


def test_heavy_member_has_no_negative_macros(client):
    signup(client)
    m = add_member(client, **dict(ADULT, weight_kg=150, goal="lose", kg_per_week=1.0, activity="sedentary"))
    assert m["targets"]["carbs_g"] >= 0


def test_household_limited_to_eight_members(client):
    signup(client)
    for i in range(8):
        add_member(client, **dict(ADULT, name=f"P{i}"))
    assert client.post("/api/members", json=ADULT).status_code == 409


def test_update_and_delete_member(client):
    signup(client)
    m = add_member(client, **ADULT)
    r = client.put(f"/api/members/{m['id']}", json=dict(ADULT, weight_kg=90))
    assert r.status_code == 200 and r.json()["weight_kg"] == 90
    assert client.delete(f"/api/members/{m['id']}").status_code == 204
    assert client.get("/api/members").json() == []


def test_unknown_fields_are_rejected(client):
    signup(client)
    assert client.post("/api/members", json=dict(ADULT, is_admin=True)).status_code == 422


# ---- recipes
def test_seed_recipes_are_listed_with_computed_macros(client):
    signup(client)
    recipes = client.get("/api/recipes").json()
    assert len(recipes) >= 30
    assert all(r["is_global"] and r["complete"] for r in recipes)
    assert all(r["macros_per_serving"]["kcal"] > 0 for r in recipes)


def test_recipe_filters(client):
    signup(client)
    easy = client.get("/api/recipes?difficulty=easy").json()
    assert easy and all(r["difficulty"] == "easy" for r in easy)
    quick = client.get("/api/recipes?max_minutes=15&meal_type=breakfast").json()
    assert quick and all(r["total_minutes"] <= 15 and "breakfast" in r["meal_types"] for r in quick)
    assert [r["title"] for r in client.get("/api/recipes?q=shakshuka").json()] == ["Shakshuka"]


def test_create_recipe_computes_macros_and_total_time(client):
    signup(client)
    r = client.post("/api/recipes", json=BASE_RECIPE)
    assert r.status_code == 201
    body = r.json()
    assert body["total_minutes"] == 7
    assert body["complete"] and body["macros_per_serving"]["kcal"] == round(143 * 100 / 100)  # 2 eggs = 100 g
    assert body["is_global"] is False


def test_unknown_ingredient_makes_recipe_incomplete_until_custom_nutrition_added(client):
    signup(client)
    recipe = dict(BASE_RECIPE, ingredients=[LINE, {"name": "grandma sauce", "quantity": 50, "unit": "g"}])
    created = client.post("/api/recipes", json=recipe).json()
    assert created["complete"] is False
    assert created["missing_nutrition"] == ["grandma sauce"]
    assert created["macros_per_serving"] is None

    client.post("/api/ingredients", json={"name": "Grandma sauce", "kcal": 120, "protein": 2, "carbs": 15, "fat": 6})
    fixed = client.get(f"/api/recipes/{created['id']}").json()
    assert fixed["complete"] is True
    assert fixed["macros_per_serving"]["kcal"] == round(143 + 60)


def test_manual_macro_override_makes_recipe_complete(client):
    signup(client)
    recipe = dict(
        BASE_RECIPE,
        ingredients=[{"name": "mystery", "quantity": 1, "unit": "piece"}],
        macro_override={"kcal": 450, "protein": 30, "carbs": 40, "fat": 15},
    )
    body = client.post("/api/recipes", json=recipe).json()
    assert body["complete"] and body["has_override"] and body["macros_per_serving"]["kcal"] == 450


def test_global_recipes_are_read_only_but_can_be_copied(client):
    signup(client)
    seed = client.get("/api/recipes?q=shakshuka").json()[0]
    assert client.put(f"/api/recipes/{seed['id']}", json=BASE_RECIPE).status_code == 403
    assert client.delete(f"/api/recipes/{seed['id']}").status_code == 403
    copy = client.post(f"/api/recipes/{seed['id']}/copy")
    assert copy.status_code == 201
    body = copy.json()
    assert not body["is_global"] and body["ingredients"] == seed["ingredients"]
    edited = client.put(f"/api/recipes/{body['id']}", json=dict(BASE_RECIPE, title="Better shakshuka"))
    assert edited.status_code == 200 and edited.json()["title"] == "Better shakshuka"


def test_deleting_an_unplanned_recipe_removes_it(client):
    signup(client)
    rid = client.post("/api/recipes", json=BASE_RECIPE).json()["id"]
    assert client.delete(f"/api/recipes/{rid}").json() == {"deleted": True, "archived": False}
    assert client.get(f"/api/recipes/{rid}").status_code == 404


def test_planned_recipe_is_archived_not_deleted(family):
    client, _ = family
    rid = client.post("/api/recipes", json=dict(BASE_RECIPE, meal_types=["breakfast"])).json()["id"]
    r = client.put("/api/plan/2026-11-02/breakfast", json={"recipe_id": rid})
    assert r.status_code == 200
    assert client.delete(f"/api/recipes/{rid}").json() == {"deleted": False, "archived": True}
    assert rid not in [x["id"] for x in client.get("/api/recipes").json()]
    assert rid in [x["id"] for x in client.get("/api/recipes?include_archived=true").json()]
    # an archived recipe can no longer be planned
    assert client.put("/api/plan/2026-11-03/breakfast", json={"recipe_id": rid}).status_code == 422


@pytest.mark.parametrize(
    "patch",
    [
        {"servings": 0},
        {"ingredients": []},
        {"meal_types": []},
        {"difficulty": "impossible"},
        {"ingredients": [{"name": "egg", "quantity": 1, "unit": "pinch"}]},
        {"ingredients": [{"name": "egg", "quantity": -1, "unit": "g"}]},
    ],
)
def test_invalid_recipes_are_rejected(client, patch):
    signup(client)
    assert client.post("/api/recipes", json=dict(BASE_RECIPE, **patch)).status_code == 422


def test_ingredient_autocomplete(client):
    signup(client)
    results = client.get("/api/ingredients?q=chick").json()
    assert {"chicken breast", "chickpeas"} <= {r["name"] for r in results}
    chicken = next(r for r in results if r["name"] == "chicken breast")
    assert "piece" not in chicken["units"] and "cup" not in chicken["units"]
    assert client.get("/api/ingredients?q=").json() == []
