import threading

from fastapi.testclient import TestClient

from app.server import create_app


def alert(fingerprint="f1", status="firing", name="ShoppingListFailureRate"):
    return {"status": status, "fingerprint": fingerprint, "labels": {"alertname": name}, "annotations": {}}


def payload(*alerts):
    return {"alerts": list(alerts)}


def make(settings, runner):
    return TestClient(create_app(settings, runner=runner))


def test_firing_alert_runs_the_responder_once(settings):
    runs = []
    client = make(settings, lambda s, a: runs.append(a) or {"status": "resolved"})
    r = client.post("/alert", json=payload(alert()))
    assert r.json() == {"accepted": True, "alerts": 1}
    assert len(runs) == 1  # background task has completed by the time TestClient returns
    incidents = client.get("/incidents").json()
    assert incidents["busy"] is False and incidents["incidents"][0]["status"] == "resolved"


def test_resolved_notifications_do_not_wake_the_agent(settings):
    runs = []
    client = make(settings, lambda s, a: runs.append(a) or {"status": "resolved"})
    r = client.post("/alert", json=payload(alert(status="resolved")))
    assert r.json()["accepted"] is False and runs == []


def test_repeat_notifications_for_the_same_alert_are_ignored(settings):
    runs = []
    client = make(settings, lambda s, a: runs.append(a) or {"status": "resolved"})
    client.post("/alert", json=payload(alert("same")))
    again = client.post("/alert", json=payload(alert("same")))
    assert again.json() == {"accepted": False, "reason": "duplicate: already handled recently"}
    assert len(runs) == 1
    other = client.post("/alert", json=payload(alert("different")))
    assert other.json()["accepted"] is True and len(runs) == 2


def test_cooldown_expiry_allows_the_same_alert_again(settings):
    from dataclasses import replace

    runs = []
    client = make(replace(settings, cooldown_seconds=0), lambda s, a: runs.append(a) or {"status": "resolved"})
    client.post("/alert", json=payload(alert("same")))
    client.post("/alert", json=payload(alert("same")))
    assert len(runs) == 2


def test_only_one_incident_runs_at_a_time(settings):
    started, release = threading.Event(), threading.Event()

    def slow(s, a):
        started.set()
        release.wait(5)
        return {"status": "resolved"}

    app = create_app(settings, runner=slow)
    lock = app.state.responder["lock"]
    assert lock.acquire(blocking=False)  # simulate a run in progress
    try:
        client = TestClient(app)
        r = client.post("/alert", json=payload(alert("new")))
        assert r.json() == {"accepted": False, "reason": "busy: an incident is already being handled"}
        assert client.get("/incidents").json()["busy"] is True
    finally:
        lock.release()
        release.set()


def test_a_crashing_runner_is_recorded_and_releases_the_lock(settings):
    def boom(s, a):
        raise RuntimeError("kaboom")

    client = make(settings, boom)
    client.post("/alert", json=payload(alert("c1")))
    state = client.get("/incidents").json()
    assert state["busy"] is False
    assert state["incidents"][0]["status"] == "crashed"
    assert client.post("/alert", json=payload(alert("c2"))).json()["accepted"] is True  # still usable


def test_health_reports_mode(settings):
    assert make(settings, lambda s, a: {}).get("/health").json() == {"status": "ok", "mode": "playbook"}
