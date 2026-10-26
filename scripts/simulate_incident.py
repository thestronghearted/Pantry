#!/usr/bin/env python3
"""Incident drill: ship a "bad release", let real-looking users hit it, and watch the system react.

    py scripts/dev.py simulate-incident

What happens, with the stack from `dev.py up` running:
  1. A demo household signs up and plans a week that includes a cup-measured recipe.
  2. Steady shopping-list traffic proves the app is healthy.
  3. The `shopping_list_v2` flag is switched on (the "bad release"): shopping lists start failing with 500s.
  4. Prometheus fires ShoppingListFailureRate -> Alertmanager -> the responder agent wakes up.
  5. The responder rolls the flag back, proves recovery with a synthetic probe and writes an incident report.
  6. This script confirms real traffic is healthy again and prints the report.
"""
from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = "http://localhost:8080"
PROM = "http://localhost:9091"
RESPONDER = "http://localhost:9000"
TIMEOUT_SECONDS = 420


def env() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


class Client:
    """Minimal cookie-keeping JSON client (stdlib only, so the drill needs no installs)."""

    def __init__(self, base: str):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method: str, path: str, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with self.opener.open(req, timeout=15) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, None


def get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def monday() -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def stamp(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)


def main() -> int:
    cfg = env()
    admin = {"X-Admin-Token": cfg["ADMIN_TOKEN"]}
    t0 = time.time()

    for name, url in (("app", f"{APP}/ready"), ("responder", f"{RESPONDER}/health"), ("prometheus", f"{PROM}/-/ready")):
        if get_json(url) is None and name != "prometheus":
            print(f"{name} is not reachable at {url}. Start the stack first: py scripts/dev.py up", file=sys.stderr)
            return 2

    admin_client = Client(APP)
    status, flags = admin_client.call("GET", "/admin/flags", headers=admin)
    if status != 200:
        print("Could not read flags with ADMIN_TOKEN from .env. Is the stack running with the same .env?", file=sys.stderr)
        return 2
    admin_client.call("PUT", "/admin/flags/shopping_list_v2", {"enabled": False}, headers=admin)

    # 1. a demo household with a plan that includes cups
    user = Client(APP)
    password = "drill-" + secrets.token_urlsafe(12)  # throwaway local test credential, never printed
    email = f"drill-{secrets.token_hex(3)}@pantry-drill.com"
    s, _ = user.call("POST", "/api/auth/signup", {"household_name": "Drill household", "email": email, "password": password})
    if s != 201:
        print(f"signup failed ({s})", file=sys.stderr)
        return 2
    user.call("POST", "/api/members", {"name": "Dana", "sex": "female", "age": 36, "height_cm": 168, "weight_kg": 74,
                                       "activity": "light", "goal": "lose", "kg_per_week": 0.4})
    week = monday()
    s, _ = user.call("POST", "/api/plan/generate", {"week_start": week, "max_difficulty": "easy", "max_minutes_per_day": 90, "seed": 3})
    _, recipes = user.call("GET", "/api/recipes?q=overnight")
    if recipes:  # make sure the plan uses a recipe measured in cups
        user.call("PUT", f"/api/plan/{week}/breakfast", {"recipe_id": recipes[0]["id"]})
    stamp(f"demo household ready, week {week}", t0)

    def request_list() -> int:
        return user.call("GET", f"/api/shopping-list?week={week}")[0]

    def traffic(seconds: float, label: str) -> dict:
        codes: dict[int, int] = {}
        end = time.time() + seconds
        while time.time() < end:
            c = request_list()
            codes[c] = codes.get(c, 0) + 1
            time.sleep(0.3)
        stamp(f"{label}: {dict(sorted(codes.items()))}", t0)
        return codes

    # 2. healthy baseline
    base = traffic(20, "baseline traffic (status: count)")
    if base.get(200, 0) == 0:
        print("The shopping list is not healthy before the drill started; aborting.", file=sys.stderr)
        return 2

    # 3. the bad release
    admin_client.call("PUT", "/admin/flags/shopping_list_v2", {"enabled": True}, headers=admin)
    stamp("BAD RELEASE: shopping_list_v2 switched on -> shopping lists will fail for users", t0)

    # 4./5. keep real traffic flowing while the alert and responder do their work
    seen_alert = seen_incident = False
    recovered_at = None
    incident = None
    deadline = time.time() + TIMEOUT_SECONDS
    last_status = None
    while time.time() < deadline:
        code = request_list()
        if code != last_status:
            stamp(f"user request now returns {code}", t0)
            last_status = code
        alerts = (get_json(f"{PROM}/api/v1/alerts") or {}).get("data", {}).get("alerts", [])
        state = next((a["state"] for a in alerts if a["labels"].get("alertname") == "ShoppingListFailureRate"), None)
        if state and not seen_alert:
            stamp(f"Prometheus alert ShoppingListFailureRate is {state}", t0)
        if state == "firing" and not seen_alert:
            seen_alert = True
            stamp("alert FIRING -> Alertmanager -> responder webhook", t0)
        incidents = (get_json(f"{RESPONDER}/incidents") or {}).get("incidents", [])
        if incidents and not seen_incident:
            seen_incident = True
            incident = incidents[-1]
            stamp(f"responder handled the incident: status={incident.get('status')} mode={incident.get('mode')}", t0)
        if seen_incident and code == 200 and recovered_at is None:
            recovered_at = time.time()
            stamp("real users are getting their shopping list again", t0)
        if recovered_at and time.time() - recovered_at > 5:
            break
        time.sleep(1)

    print()
    if not (seen_alert and seen_incident and recovered_at):
        print("DRILL INCOMPLETE:", {"alert_fired": seen_alert, "responder_ran": seen_incident, "recovered": bool(recovered_at)})
        print("Check:  py scripts/dev.py logs responder   and   http://localhost:9091/alerts")
        return 1

    final_flags = admin_client.call("GET", "/admin/flags", headers=admin)[1]
    print("Flags after the incident:", {f["name"]: f["enabled"] for f in final_flags})
    print("Timeline from the responder:")
    for line in incident.get("timeline", []):
        print("  -", line)
    report = incident.get("report")
    if report:
        local = ROOT / "incident-reports" / Path(report).name
        if local.exists():
            print(f"\nIncident report ({local.relative_to(ROOT)}):\n")
            print(local.read_text(encoding="utf-8"))
    print(f"DRILL PASSED: alert fired, responder acted ({incident.get('status')}), users recovered in {time.time() - t0:.0f}s total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
