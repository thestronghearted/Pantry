# Architecture

## Shape
One container image serves both the React app and the API, so the browser talks to a single origin. That keeps cookies, CORS and tracing simple and makes local and production behave the same.

```
Browser ──> FastAPI (uvicorn)
              ├─ /api/*        JSON API, session cookie auth
              ├─ /metrics      Prometheus (OpenMetrics with exemplars)
              ├─ /health /ready
              ├─ /admin/*      feature flags (only when ADMIN_TOKEN is set)
              └─ /*            built React app (single-page fallback)
            └─> Postgres (SQLAlchemy 2, Alembic)
```

## Code layout (`backend/app`)
| Path | Role |
|---|---|
| `domain/` | **Pure functions, no I/O.** `targets` (calorie/macro maths), `nutrition` (catalog, unit conversion, recipe macros), `portions` (meal split, portion sizing), `planner` (weekly plan), `shopping` (aggregation). Most unit tests live here. |
| `routers/` | HTTP layer: `auth`, `members`, `recipes` (+ingredients), `plan`, `shopping`, `admin`. |
| `services.py` | Glue between database rows and domain functions; builds API views. |
| `models.py`, `db.py` | Tables; engine; migration runner (Postgres advisory lock). |
| `flags.py` | Feature flags stored in the database, cached 5 s so every instance converges. |
| `telemetry.py`, `metrics.py` | JSON logs with trace ids, redaction, tracing setup, journey metrics. |
| `security.py` | argon2 hashing, rate limiter, constant-time token comparison. |
| `seeding.py`, `seed/` | Bundled nutrition table (JSON, in memory) and recipes (idempotent DB seed); optional probe household. |

## Data model
`households` 1─* `users`, `members`, `recipes` (own copies; `household_id` NULL = bundled), `ingredients` (custom nutrition), `plan_meals` (one per household/day/meal) 1─* `plan_portions` (per member), `shopping_checks` (household, week, item key), plus `feature_flags`.

Every query that touches household data filters by `household_id`; another household's resource returns 404 so existence is not leaked. A recipe referenced by a plan cannot be deleted (database foreign key); the API archives it instead.

## Key decisions
| Decision | Why |
|---|---|
| Domain logic as pure functions | Fast, exhaustive unit tests; no database needed to test the planner or shopping list. |
| Macros computed, not stored | Editing an ingredient or the nutrition table updates every recipe; no stale numbers. |
| Plan per week, Monday start | One consistent unit for the plan, shopping list and ticks. |
| Portions are chosen per person, per day | Brute force over at most 7³ combinations finds the exact best fit; deterministic and testable. |
| Sessions in a signed cookie | No session table; cookie is `httpOnly`, `SameSite=Lax`, `Secure` in production. |
| Alembic with expand/contract migrations | The previous image must still run against the newer schema, so rollback is safe. |
| Feature flags in the database | All instances see a rollback; used by the responder. |
| Telemetry via OpenTelemetry + Prometheus client | Traces/logs travel OTLP; metrics use stable names that alert rules depend on. |

## Planning algorithm (summary)
1. Candidate recipes: complete macros, not archived, right meal type, difficulty ≤ limit, total minutes ≤ daily limit.
2. For each day, take the four best-fitting recipes per meal (excluding recent repeats), try every combination whose cooking time fits.
3. For each member, choose portions (0.5-2.0 in 0.25 steps) minimising distance to their **daily** target, preferring the 25/35/40% meal split.
4. Pick the combination with the smallest average error; flag the day `off_target` if anyone is more than 10% away.

## What runs where
| Environment | Components |
|---|---|
| Local (`dev.py up`) | app, Postgres, OTel Collector, Tempo, Loki, Prometheus, Alertmanager, Grafana, responder |
| Dev / Prod (Render + Neon) | app image, managed Postgres. Telemetry export is off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set. |
