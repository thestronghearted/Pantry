"""Deterministic runbook used when no ANTHROPIC_API_KEY is configured (and as the agent's safety net)."""
from __future__ import annotations

import json

from .tools import ROLLBACK_FLAGS, Toolbox

ERROR_RATIO = (
    'sum(rate(journey_requests_total{journey="shopping_list",outcome="error",synthetic="false"}[2m])) '
    '/ sum(rate(journey_requests_total{journey="shopping_list",synthetic="false"}[2m]))'
)
RECENT_ERRORS = '{service_name="pantry-api"} | severity_text="ERROR"'


def run_playbook(tools: Toolbox, alert_name: str) -> str:
    """Investigate, roll back a known-bad flag, verify, report. Returns the final status."""
    for query in (lambda: tools.query_prometheus(ERROR_RATIO), lambda: tools.query_loki(RECENT_ERRORS)):
        try:
            query()
        except Exception as exc:  # evidence is best-effort; the fix must not depend on it
            tools.actions.append(f"evidence query failed: {type(exc).__name__}")

    try:
        flags = json.loads(tools.get_flags())
    except Exception as exc:
        return _escalate(tools, f"Could not read feature flags ({type(exc).__name__}).", alert_name)

    risky = [f["name"] for f in flags if f["enabled"] and f["name"] in ROLLBACK_FLAGS]
    if not risky:
        return _escalate(tools, "No known risky feature flag is enabled, so there is no safe automatic rollback.", alert_name)

    for name in risky:
        tools.set_flag(name, False)

    probe = json.loads(tools.probe_journey())
    if not probe.get("ok"):
        return _escalate(tools, f"Rolled back {', '.join(risky)} but the synthetic probe still fails ({probe}).", alert_name,
                         actions=[f"switched off flag {n}" for n in risky])

    tools.write_incident_report(
        status="resolved",
        summary=f"{alert_name}: shopping-list requests were failing for real users.",
        root_cause=f"Feature flag(s) {', '.join(risky)} were enabled. The shopping_list_v2 code path fails on cup-measured ingredients.",
        actions=[f"Switched off flag {n} (rollback)." for n in risky] + ["Verified recovery with the synthetic shopping-list probe."],
        follow_ups=["Fix the missing 'cup' unit in the v2 conversion table and add a regression test before re-enabling."],
    )
    return tools.status or "resolved"


def _escalate(tools: Toolbox, reason: str, alert_name: str, actions: list[str] | None = None) -> str:
    tools.write_incident_report(
        status="needs_human",
        summary=f"{alert_name}: automatic remediation did not apply.",
        root_cause=reason,
        actions=actions or ["Collected metrics, logs and flag state."],
        follow_ups=["A human should investigate; see the evidence below and the application logs."],
    )
    return tools.status or "needs_human"
