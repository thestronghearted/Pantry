# Runbook

## ShoppingListFailureRate
**Meaning:** more than 5% of real users' shopping-list requests are failing with a server error.
**User impact:** families cannot open their list, which matters most in the shop.

### What the responder agent does automatically
1. Reads the error ratio (Prometheus) and recent ERROR logs (Loki), and lists feature flags.
2. If a risky flag it is allowed to change is on (`shopping_list_v2`), switches it **off** (rollback). It cannot turn anything on or change anything else.
3. Runs a synthetic probe: logs in as the probe household and requests a shopping list that uses cup-measured ingredients (the failing path). Retries for ~12 s while other instances pick up the flag.
4. Writes an incident report to `incident-reports/` (local) and declares **resolved** only if the probe passed after the last change.
5. If there is no known cause, or the probe still fails: report with status **needs human**, plus a GitHub issue (labels `incident`, `needs-human`) when `GITHUB_TOKEN` is configured.

Modes: with `ANTHROPIC_API_KEY` a Claude tool-use loop decides the steps (same tools, same guardrails); without it a deterministic playbook runs. If the LLM call fails, the playbook takes over.

### Guardrails (enforced in code, `responder/app/tools.py`)
- Only the listed tools exist; unknown tool names are refused.
- `set_flag` accepts only `enabled=false` for flags in an allow-list.
- `write_incident_report(status="resolved")` is refused unless a probe passed after the last change.
- Tool output from logs and metrics is truncated and wrapped as untrusted data.
- Webhook handling: ignores `resolved`, de-duplicates by alert fingerprint (10-minute cooldown), one incident at a time, a crashing run is recorded and releases the lock.

### If you are the human
1. Open `http://localhost:9000/incidents` and the latest file in `incident-reports/`.
2. Grafana → *User journeys*: error panel and latency exemplars → open a trace → "logs for this trace".
3. Check flags: `curl -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8080/admin/flags`.
4. For a bad deploy in dev/prod: run the **Rollback** workflow with the previous `sha-…` tag ([DEPLOY.md](DEPLOY.md#rollback)).
5. Follow-up: add a regression test, fix, and re-enable behind the flag.

### Reproduce the whole flow
```bash
py scripts/dev.py up
py scripts/dev.py simulate-incident
```
The drill signs up a throwaway household, plans a week with a cup-measured recipe, then switches on `shopping_list_v2` (the bad release). It prints when users start failing, when the alert fires, what the responder did, and when users recover.

## Other things that can go wrong
| Symptom | Check |
|---|---|
| App not ready | `py scripts/dev.py logs app`; `/ready` fails when the database is unreachable |
| No traces/logs in Grafana | `py scripts/dev.py logs otel-collector`; `OTEL_EXPORTER_OTLP_ENDPOINT` set on the app? |
| Alert never fires | Prometheus → Status → Rules; needs traffic of at least 0.02 req/s, and flag must actually break the user's week (a plan using cups) |
| Responder says `needs_human` | No risky flag was on, so the cause is something else: read the report's evidence section |
