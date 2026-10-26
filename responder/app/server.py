"""Alertmanager webhook. Wakes the responder, one incident at a time, without repeating itself."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI

from .agent import run_agent
from .config import Settings
from .escalation import open_issue
from .playbook import run_playbook
from .tools import Toolbox

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}')
log = logging.getLogger("responder")


def default_runner(settings: Settings, alerts: list[dict]) -> dict:
    """Handle one incident: LLM agent when a key exists, otherwise the deterministic playbook."""
    tools = Toolbox(settings)
    names = ", ".join(sorted({a.get("labels", {}).get("alertname", "alert") for a in alerts})) or "alert"
    mode = "playbook"
    if settings.anthropic_api_key:
        import anthropic

        mode = "llm"
        status = run_agent(anthropic.Anthropic(api_key=settings.anthropic_api_key), settings.model, alerts, tools, settings.max_steps)
    else:
        status = run_playbook(tools, names)
    issue = open_issue(settings, f"Incident needs a human: {names}", tools.report_path) if status == "needs_human" else None
    return {
        "alerts": names, "mode": mode, "status": status,
        "report": str(tools.report_path) if tools.report_path else None,
        "issue": issue, "timeline": tools.actions,
    }


def create_app(settings: Settings | None = None, runner: Callable[[Settings, list[dict]], dict] = default_runner) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Pantry Plan responder")
    state = {"lock": threading.Lock(), "seen": {}, "incidents": []}
    app.state.responder = state

    def handle(alerts: list[dict], fingerprints: list[str]) -> None:
        # Hold the lock for the whole run: a second alert must not start a second agent.
        try:
            started = datetime.now(timezone.utc).isoformat()
            log.info("incident started: %s", [a.get("labels", {}).get("alertname") for a in alerts])
            try:
                outcome = runner(settings, alerts)
            except Exception as exc:  # the responder itself must never die silently
                log.exception("runner crashed")
                outcome = {"status": "crashed", "error": type(exc).__name__}
            outcome.update(started=started, finished=datetime.now(timezone.utc).isoformat(), fingerprints=fingerprints)
            state["incidents"].append(outcome)
            log.info("incident finished: %s", outcome.get("status"))
        finally:
            state["lock"].release()

    @app.post("/alert")
    def alert(payload: dict, background: BackgroundTasks):
        firing = [a for a in payload.get("alerts", []) if a.get("status") == "firing"]
        if not firing:  # 'resolved' notifications never wake the agent
            return {"accepted": False, "reason": "no firing alerts"}
        now = time.monotonic()
        fresh = [a for a in firing if now - state["seen"].get(a.get("fingerprint", ""), -1e9) > settings.cooldown_seconds]
        if not fresh:
            return {"accepted": False, "reason": "duplicate: already handled recently"}
        if not state["lock"].acquire(blocking=False):
            return {"accepted": False, "reason": "busy: an incident is already being handled"}
        prints = [a.get("fingerprint", "") for a in fresh]
        for p in prints:
            state["seen"][p] = now
        background.add_task(handle, fresh, prints)
        return {"accepted": True, "alerts": len(fresh)}

    @app.get("/incidents")
    def incidents():
        return {"busy": state["lock"].locked(), "incidents": state["incidents"]}

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "llm" if settings.anthropic_api_key else "playbook"}

    return app


def app_factory() -> FastAPI:
    return create_app()
