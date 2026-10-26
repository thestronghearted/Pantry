from datetime import date, timedelta

from .conftest import MONDAY, add_member, ADULT, generate, signup


def test_generate_requires_a_member(client):
    signup(client)
    r = client.post("/api/plan/generate", json={"week_start": MONDAY})
    assert r.status_code == 422 and "member" in r.json()["detail"]


def test_generate_rejects_non_monday(family):
    client, _ = family
    r = client.post("/api/plan/generate", json={"week_start": "2026-11-03"})
    assert r.status_code == 422 and "Monday" in r.json()["detail"]


def test_generated_week_respects_limits_and_targets(family):
    client, members = family
    plan = generate(client)
    assert [d["date"] for d in plan["days"]] == [(date.fromisoformat(MONDAY) + timedelta(days=i)).isoformat() for i in range(7)]
    easy_ids = {r["id"] for r in client.get("/api/recipes?difficulty=easy").json()}
    filled = [d for d in plan["days"] if d["slots"]]
    assert len(filled) == 7
    for day in filled:
        assert day["cooking_minutes"] <= 120
        assert [s["meal"] for s in day["slots"]] == ["breakfast", "lunch", "dinner"]
        for slot in day["slots"]:
            assert slot["recipe"]["id"] in easy_ids
            assert len(slot["portions"]) == 3
            assert all(0.5 <= p["servings"] <= 2.0 for p in slot["portions"])
    on_target = [d for d in filled if not d["off_target"]]
    assert len(on_target) >= 6
    for day in on_target:
        for total in day["totals"]:
            assert total["error"] <= 0.10
    assert plan["weekly_cooking_minutes"] == sum(d["cooking_minutes"] for d in plan["days"])


def test_portions_differ_by_member_size(family):
    client, members = family
    plan = generate(client)
    dinner = plan["days"][0]["slots"][2]["portions"]
    by_member = {p["member_id"]: p["servings"] for p in dinner}
    assert by_member[members[0]["id"]] >= by_member[members[1]["id"]]


def test_regenerating_replaces_the_week(family):
    client, _ = family
    first = generate(client, seed=1)
    second = generate(client, seed=2)
    pick = lambda p: [[s["recipe"]["id"] for s in d["slots"]] for d in p["days"]]
    assert pick(first) != pick(second)
    assert client.get(f"/api/plan?week={MONDAY}").json() == second


def test_impossible_limits_give_helpful_error(family):
    client, _ = family
    r = client.post("/api/plan/generate", json={"week_start": MONDAY, "max_minutes_per_day": 10})
    assert r.status_code == 422 and "No recipes fit" in r.json()["detail"]


def test_member_not_eating_a_meal_gets_zero_portion(family):
    client, members = family
    kid = members[2]["id"]
    eats = {str(members[0]["id"]): ["breakfast", "lunch", "dinner"], str(members[1]["id"]): ["breakfast", "lunch", "dinner"],
            str(kid): ["breakfast", "dinner"]}
    plan = generate(client, eats=eats)
    lunch = plan["days"][0]["slots"][1]
    kid_portion = next(p for p in lunch["portions"] if p["member_id"] == kid)
    assert kid_portion["skipped"] and kid_portion["servings"] == 0


def test_swap_slot_rebalances_portions(family):
    client, members = family
    plan = generate(client)
    day = plan["days"][0]
    options = client.get("/api/recipes?difficulty=easy&meal_type=dinner").json()
    current = day["slots"][2]["recipe"]["id"]
    other = next(r for r in options if r["id"] != current)
    swapped = client.put(f"/api/plan/{day['date']}/dinner", json={"recipe_id": other["id"]})
    assert swapped.status_code == 200
    new_day = swapped.json()["days"][0]
    assert new_day["slots"][2]["recipe"]["id"] == other["id"]
    for total in new_day["totals"]:
        assert total["error"] is not None


def test_edit_portion_and_skip_via_api(family):
    client, members = family
    generate(client)
    mid = members[0]["id"]
    r = client.put(f"/api/plan/{MONDAY}/lunch/portions", json={"member_id": mid, "servings": 1.5})
    portion = next(p for p in r.json()["days"][0]["slots"][1]["portions"] if p["member_id"] == mid)
    assert portion["servings"] == 1.5 and not portion["skipped"]
    r = client.put(f"/api/plan/{MONDAY}/lunch/portions", json={"member_id": mid, "skipped": True})
    portion = next(p for p in r.json()["days"][0]["slots"][1]["portions"] if p["member_id"] == mid)
    assert portion["skipped"] and portion["servings"] == 0
    assert client.put(f"/api/plan/{MONDAY}/lunch/portions", json={"member_id": mid, "servings": 1.1}).status_code == 422


def test_clear_slot(family):
    client, _ = family
    generate(client)
    r = client.delete(f"/api/plan/{MONDAY}/lunch")
    assert [s["meal"] for s in r.json()["days"][0]["slots"]] == ["breakfast", "dinner"]
    assert client.delete(f"/api/plan/{MONDAY}/lunch").status_code == 404


# ---- shopping list
def planned_single_recipe(client, recipe_body, portions):
    """One adult, one planned meal with an explicit portion, so the shopping list can be checked by hand."""
    rid = client.post("/api/recipes", json=recipe_body).json()["id"]
    r = client.put(f"/api/plan/{MONDAY}/{recipe_body['meal_types'][0]}", json={"recipe_id": rid})
    assert r.status_code == 200, r.text
    mid = client.get("/api/members").json()[0]["id"]
    client.put(f"/api/plan/{MONDAY}/{recipe_body['meal_types'][0]}/portions", json={"member_id": mid, "servings": portions})
    return rid


def test_shopping_list_scales_by_portions_and_rounds_up_countables(client):
    signup(client)
    add_member(client, **ADULT)
    planned_single_recipe(
        client,
        {
            "title": "Eggs and rice", "servings": 2, "prep_minutes": 2, "cook_minutes": 5, "difficulty": "easy",
            "meal_types": ["breakfast"],
            "ingredients": [
                {"name": "egg", "quantity": 3, "unit": "piece"},
                {"name": "chicken breast", "quantity": 300, "unit": "g"},
            ],
        },
        portions=1.75,
    )
    items = {i["name"]: i for i in client.get(f"/api/shopping-list?week={MONDAY}").json()["items"]}
    assert items["chicken breast"]["quantity"] == 263  # 300 * 1.75 / 2 = 262.5 -> 263
    assert (items["egg"]["quantity"], items["egg"]["unit"]) == (3, "piece")  # 2.625 -> 3


def test_skipping_a_meal_reduces_the_list(family):
    client, members = family
    plan = generate(client)
    before = {i["key"]: i["quantity"] for i in client.get(f"/api/shopping-list?week={MONDAY}").json()["items"]}
    kid = members[2]["id"]
    for day in plan["days"]:
        client.put(f"/api/plan/{day['date']}/dinner/portions", json={"member_id": kid, "skipped": True})
    after = {i["key"]: i["quantity"] for i in client.get(f"/api/shopping-list?week={MONDAY}").json()["items"]}
    assert sum(after.values()) < sum(before.values())


def test_shopping_list_groups_by_aisle_and_is_sorted(family):
    client, _ = family
    generate(client)
    items = client.get(f"/api/shopping-list?week={MONDAY}").json()["items"]
    order = ["produce", "dairy", "meat_fish", "pantry", "frozen", "other"]
    assert items
    assert [order.index(i["aisle"]) for i in items] == sorted(order.index(i["aisle"]) for i in items)
    assert len({i["key"] for i in items}) == len(items)


def test_ticks_persist_and_toggle(family):
    client, _ = family
    generate(client)
    key = client.get(f"/api/shopping-list?week={MONDAY}").json()["items"][0]["key"]
    assert client.put("/api/shopping-list/checks", json={"week": MONDAY, "key": key, "checked": True}).status_code == 204
    assert client.put("/api/shopping-list/checks", json={"week": MONDAY, "key": key, "checked": True}).status_code == 204  # idempotent
    items = client.get(f"/api/shopping-list?week={MONDAY}").json()["items"]
    assert [i["checked"] for i in items if i["key"] == key] == [True]
    client.put("/api/shopping-list/checks", json={"week": MONDAY, "key": key, "checked": False})
    items = client.get(f"/api/shopping-list?week={MONDAY}").json()["items"]
    assert [i["checked"] for i in items if i["key"] == key] == [False]


def test_week_without_a_plan_returns_empty_list(family):
    client, _ = family
    r = client.get("/api/shopping-list?week=2027-03-01")
    assert r.status_code == 200 and r.json()["items"] == []


def test_shopping_list_requires_monday(family):
    client, _ = family
    assert client.get("/api/shopping-list?week=2026-11-04").status_code == 422
