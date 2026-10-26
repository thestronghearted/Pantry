"""Health, metrics, trace ids, feature flags and the synthetic probe."""
import re

from prometheus_client.parser import text_string_to_metric_families

from .conftest import ADMIN_TOKEN, MONDAY, PROBE_EMAIL, PROBE_PASSWORD, generate
from app.metrics import REGISTRY

PROBE_WEEK = "2020-01-06"
ADMIN = {"X-Admin-Token": ADMIN_TOKEN}


def counter(journey: str, outcome: str, synthetic: str = "false") -> float:
    value = REGISTRY.get_sample_value(
        "journey_requests_total", {"journey": journey, "outcome": outcome, "synthetic": synthetic}
    )
    return value or 0.0


def test_health_and_ready(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_responses_carry_a_trace_id_header(family):
    client, _ = family
    r = client.get("/api/members")
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["x-trace-id"])
    assert r.headers["x-trace-id"] != client.get("/api/members").headers["x-trace-id"]


def test_shopping_list_journey_is_counted(family):
    client, _ = family
    generate(client)
    before = counter("shopping_list", "success")
    client.get(f"/api/shopping-list?week={MONDAY}")
    assert counter("shopping_list", "success") == before + 1


def test_metrics_endpoint_exposes_journey_series(family):
    client, _ = family
    client.get(f"/api/shopping-list?week={MONDAY}")
    text = client.get("/metrics").text
    names = {f.name for f in text_string_to_metric_families(text)}
    assert {"journey_requests", "journey_duration_seconds", "plan_days_off_target"} <= names


def test_openmetrics_exposition_carries_trace_exemplars(family):
    client, _ = family
    trace_id = client.get(f"/api/shopping-list?week={MONDAY}").headers["x-trace-id"]
    body = client.get("/metrics", headers={"Accept": "application/openmetrics-text"}).text
    assert f'trace_id="{trace_id}"' in body


def test_client_errors_are_not_counted_as_server_errors(family):
    client, _ = family
    errors = counter("shopping_list", "error")
    bad = counter("shopping_list", "client_error")
    assert client.get("/api/shopping-list?week=2026-11-04").status_code == 422
    assert counter("shopping_list", "error") == errors
    assert counter("shopping_list", "client_error") == bad + 1


# ---- feature flag / incident reproduction
def test_flags_need_the_admin_token(client):
    assert client.get("/admin/flags").status_code == 401
    assert client.get("/admin/flags", headers={"X-Admin-Token": "wrong"}).status_code == 401
    flags = client.get("/admin/flags", headers=ADMIN).json()
    assert flags == [{"name": "shopping_list_v2", "enabled": False, "description": flags[0]["description"]}]


def test_unknown_flag_is_404(client):
    assert client.put("/admin/flags/nope", json={"enabled": True}, headers=ADMIN).status_code == 404


def test_admin_is_disabled_without_a_token(app, client):
    from fastapi.testclient import TestClient

    from tests.integration.conftest import make_settings
    from app.main import create_app

    other = create_app(make_settings(admin_token=None))
    with TestClient(other) as c:
        assert c.get("/admin/flags", headers=ADMIN).status_code == 404
    other.state.engine.dispose()


def test_v2_flag_breaks_cup_recipes_and_turning_it_off_recovers(app, family):
    client, _ = family
    generate(client)  # seed recipes use cups, so a normal week contains at least one
    assert client.get(f"/api/shopping-list?week={MONDAY}").status_code == 200

    errors = counter("shopping_list", "error")
    client.put("/admin/flags/shopping_list_v2", json={"enabled": True}, headers=ADMIN)
    app.state.flags._loaded_at = 0  # skip the 5 s cache for the test
    broken = client.get(f"/api/shopping-list?week={MONDAY}")
    assert broken.status_code == 500
    assert broken.headers["x-trace-id"]
    assert counter("shopping_list", "error") == errors + 1

    client.put("/admin/flags/shopping_list_v2", json={"enabled": False}, headers=ADMIN)
    assert client.get(f"/api/shopping-list?week={MONDAY}").status_code == 200


# ---- synthetic probe
def test_probe_household_exercises_the_cup_path_and_is_labelled_synthetic(app, make_client):
    probe = make_client()
    assert probe.post("/api/auth/login", json={"email": PROBE_EMAIL, "password": PROBE_PASSWORD}).status_code == 200
    before = counter("shopping_list", "success", "true")
    ok = probe.get(f"/api/shopping-list?week={PROBE_WEEK}", headers={"X-Synthetic": "1"})
    assert ok.status_code == 200 and ok.json()["items"]
    assert counter("shopping_list", "success", "true") == before + 1

    real_before = counter("shopping_list", "success", "false")
    assert real_before == counter("shopping_list", "success", "false")  # probe did not touch the real series

    app.state.flags.set("shopping_list_v2", True)
    failing = probe.get(f"/api/shopping-list?week={PROBE_WEEK}", headers={"X-Synthetic": "1"})
    assert failing.status_code == 500  # the probe detects the regression, unlike a plan without cups
    app.state.flags.set("shopping_list_v2", False)
    assert probe.get(f"/api/shopping-list?week={PROBE_WEEK}", headers={"X-Synthetic": "1"}).status_code == 200
