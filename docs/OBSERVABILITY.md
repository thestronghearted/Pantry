# Observability

## The journey we watch
**Shopping list** (`GET /api/shopping-list`): the page families open in the supermarket. A second journey, **generate plan**, is instrumented the same way.

## Signals and how they connect
| Signal | Where it comes from | Where to see it |
|---|---|---|
| **Metrics** | `prometheus_client` at `/metrics`: `journey_requests_total{journey,outcome,synthetic}`, `journey_duration_seconds{journey}`, `plan_days_off_target_total` | Prometheus :9090, Grafana dashboard *User journeys* |
| **Traces** | OpenTelemetry (FastAPI + SQLAlchemy) → Collector → Tempo | Grafana → Explore → Tempo |
| **Logs** | JSON, one line per request and per journey, via OTLP → Collector → Loki (and stdout) | Grafana → Explore → Loki, panel *Errors from the API* |

**One id ties them together.** Every response carries `X-Trace-Id` (shown in the app footer). The same id is:
- the trace id in Tempo,
- the `trace_id` field on every log line (Loki structured metadata),
- an **exemplar** on the latency histogram (click a dot on the p95 graph to open the trace).

In Grafana: metric exemplar → trace → "logs for this trace"; or log line → trace.

### Outcomes
`outcome="success"`; `"client_error"` for 4xx (the user's mistake, never alerts); `"error"` for 5xx and unhandled exceptions. `synthetic="true"` marks the responder's probe (header `X-Synthetic: 1`) so probes never count as user impact.

## What is never sent to telemetry
E-mails, passwords, cookies, authorization headers, weight, height, age, request bodies. Only opaque ids (household id), route templates, status codes, durations and counts are logged. A logging filter redacts sensitive keys and masks e-mail addresses in messages and exceptions; `backend/tests/unit/test_telemetry.py` asserts it.

## Alerting
Alerts describe **user impact**, never CPU or memory.

| Alert | Condition | Why |
|---|---|---|
| `ShoppingListFailureRate` | > 5% of real shopping-list requests fail with a server error over 2 minutes, and at least 0.02 requests/second (so a couple of requests at 3 a.m. cannot page), for 30 s | Families cannot get their list |

The rule is in `observability/alerts.yml` with unit tests in `observability/alerts_test.yml` (fires on real errors; stays quiet for rare errors, probe traffic, client errors and almost-no-traffic; resolves when errors stop). Run: `py scripts/dev.py test`.

Route: Prometheus → Alertmanager → webhook `http://responder:9000/alert` (see [RUNBOOK.md](RUNBOOK.md)). Resolved notifications are not sent, so recovery never wakes the agent.

## Deployed environments
Dev and prod run the app and the database. Export is off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set (for example to a hosted Grafana Cloud endpoint); metrics are always available at `/metrics`. The complete stack, including alerting and the responder, is the local Compose system and the incident drill.
