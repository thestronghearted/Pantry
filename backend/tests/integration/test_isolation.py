"""One household must never see or touch another's data (spec F1.4)."""
from .conftest import ADULT, MONDAY, add_member, generate, signup

RECIPE = {
    "title": "Secret family stew",
    "servings": 2,
    "prep_minutes": 5,
    "cook_minutes": 20,
    "difficulty": "easy",
    "meal_types": ["dinner"],
    "ingredients": [{"name": "potato", "quantity": 400, "unit": "g"}],
    "steps": ["Boil."],
}


def test_second_household_sees_none_of_the_first(family, make_client):
    a, members = family
    recipe = a.post("/api/recipes", json=RECIPE).json()
    generate(a)
    a.put("/api/shopping-list/checks", json={"week": MONDAY, "key": "egg|piece", "checked": True})

    b = make_client()
    signup(b, email="other@example.com", name="The Joneses")

    assert b.get("/api/members").json() == []
    assert all(r["title"] != RECIPE["title"] for r in b.get("/api/recipes").json())
    plan = b.get(f"/api/plan?week={MONDAY}").json()
    assert all(day["slots"] == [] for day in plan["days"])
    assert b.get(f"/api/shopping-list?week={MONDAY}").json()["items"] == []

    # direct access by id is a 404, not a 403 (existence is not leaked)
    assert b.get(f"/api/members/{members[0]['id']}").status_code == 404
    assert b.put(f"/api/members/{members[0]['id']}", json=ADULT).status_code == 404
    assert b.delete(f"/api/members/{members[0]['id']}").status_code == 404
    assert b.get(f"/api/recipes/{recipe['id']}").status_code == 404
    assert b.put(f"/api/recipes/{recipe['id']}", json=RECIPE).status_code == 404
    assert b.delete(f"/api/recipes/{recipe['id']}").status_code == 404
    assert b.post(f"/api/recipes/{recipe['id']}/copy").status_code == 404


def test_cannot_plan_another_households_recipe_or_edit_their_portions(family, make_client):
    a, members = family
    recipe = a.post("/api/recipes", json=RECIPE).json()
    generate(a)
    day = f"{MONDAY}"

    b = make_client()
    signup(b, email="other@example.com", name="The Joneses")
    add_member(b, **ADULT)
    assert b.put(f"/api/plan/{day}/dinner", json={"recipe_id": recipe["id"]}).status_code == 404
    r = b.put(f"/api/plan/{day}/dinner/portions", json={"member_id": members[0]["id"], "servings": 2})
    assert r.status_code == 404


def test_ticks_are_per_household(family, make_client):
    a, _ = family
    generate(a)
    items = a.get(f"/api/shopping-list?week={MONDAY}").json()["items"]
    key = items[0]["key"]
    a.put("/api/shopping-list/checks", json={"week": MONDAY, "key": key, "checked": True})
    assert next(i for i in a.get(f"/api/shopping-list?week={MONDAY}").json()["items"] if i["key"] == key)["checked"]

    b = make_client()
    signup(b, email="other@example.com", name="The Joneses")
    add_member(b, **ADULT)
    generate(b)
    again = b.get(f"/api/shopping-list?week={MONDAY}").json()["items"]
    assert not any(i["checked"] for i in again)


def test_custom_ingredients_do_not_leak(family, make_client):
    a, _ = family
    a.post("/api/ingredients", json={"name": "Grandma sauce", "kcal": 100, "protein": 1, "carbs": 10, "fat": 5})
    b = make_client()
    signup(b, email="other@example.com", name="The Joneses")
    assert b.get("/api/ingredients?q=grandma").json() == []
    assert a.get("/api/ingredients?q=grandma").json()[0]["name"] == "grandma sauce"
