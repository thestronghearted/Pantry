# Backlog

Mirror of the GitHub Issues at https://github.com/thestronghearted/Pantry/issues. Published by `scripts/create_github_issues.py`.
Format (parsed by the script): `## T<nn> — title`, a `labels:` line, a `spec:` line, then an acceptance-criteria checklist.

## T01 — Repo, specs and agent docs
labels: role:product, mvp
spec: all
- [ ] SPEC.md, AGENTS.md, CLAUDE.md, PROCESS.md, AGENT_TEAM.md committed
- [ ] Backlog issues exist on GitHub with role and priority labels
- [ ] Every MVP behaviour in SPEC has a testable criterion

## T02 — Targets: calories and macros per member
labels: role:backend, mvp
spec: F2.2–F2.7
- [ ] Mifflin–St Jeor × activity − deficit matches hand-calculated examples
- [ ] Floors 1500 (male) / 1200 (female) applied and reported with effective kg/week
- [ ] Under 18 rejected for lose/maintain
- [ ] Protein capped at 35% kcal; carbs never negative (150 kg member test)

## T03 — Nutrition table and recipe macros
labels: role:backend, mvp
spec: F3.2, F3.4, F3.5
- [ ] ≥60 ingredients per 100 g with density / grams-per-piece and aisle, source cited
- [ ] Macros per serving computed from ingredients and units
- [ ] Unknown ingredient → recipe `incomplete` unless custom nutrition or override given

## T04 — Shopping-list aggregation
labels: role:backend, mvp
spec: F5.1–F5.4
- [ ] Scales by member portions ÷ recipe servings and sums duplicates
- [ ] Unit merging (g/kg, ml/l, density), aliases and plurals normalised
- [ ] Countable items rounded up; grouped by aisle

## T05 — Plan generator with family portions
labels: role:backend, mvp
spec: F4.1–F4.6, F4.8
- [ ] Respects difficulty, daily minutes, meal type, no-repeat window
- [ ] Portions in 0.25 steps within 0.5–2.0; each member within ±10% when feasible
- [ ] Infeasible days flagged `off_target`; deterministic per seed
- [ ] Default filters can fill a week from seed recipes

## T06 — Database, migrations and seed data
labels: role:backend, mvp
spec: F3.6, F3.7
- [ ] Alembic migration creates all tables; runs under a Postgres advisory lock
- [ ] Idempotent seed: nutrition table + ≥30 recipes (≥6 easy per meal type)
- [ ] Feature flags stored in DB

## T07 — Auth, sessions and household isolation
labels: role:backend, mvp
spec: F1.1–F1.6
- [ ] Signup/login/logout/me with argon2 and signed cookie
- [ ] Rate limit 429 after 10 attempts/minute/IP
- [ ] Second household gets 404 for every first-household resource (integration test)
- [ ] Delete household removes all its data

## T08 — Members and recipes API
labels: role:backend, mvp
spec: F2.1, F3.1, F3.3, F3.6–F3.8
- [ ] CRUD members (1–8) with targets endpoint
- [ ] Recipes CRUD, filters, copy-to-mine, archive when planned
- [ ] Ingredient autocomplete

## T09 — Plan and shopping-list API
labels: role:backend, mvp
spec: F4.7–F4.9, F5.5, F5.6
- [ ] Generate, read, swap slot, edit portion, skip meal
- [ ] Shopping list with persisted ticks per (household, week, item)
- [ ] Cooking time per day/week in plan response

## T10 — Frontend shell, auth and navigation
labels: role:frontend, mvp
spec: F6.1, F6.2
- [ ] Login/signup pages, session handling, bottom tab bar
- [ ] No horizontal scroll at 375 px; tap targets ≥ 44 px

## T11 — Family and recipe screens
labels: role:frontend, mvp
spec: F2, F3, F6.3
- [ ] Family screen shows members and targets with notice
- [ ] Recipe list with filters; quick-add recipe form with ingredient autocomplete and macro preview

## T12 — Plan and shopping screens
labels: role:frontend, mvp
spec: F4.7–F4.9, F5, F6.4, F6.5
- [ ] Generate week with difficulty/time limits; meal cards with portion chips and macros
- [ ] Swap, edit portion, skip
- [ ] Shopping list grouped by aisle with persistent ticks; last list cached for offline view
- [ ] Footer shows `X-Trace-Id`

## T13 — Adversarial QA and edge cases
labels: role:qa, mvp
spec: F1.4, F2.6, F4.4, F5.3
- [ ] Isolation, negative-carb, portion-bounds and rounding tests all green
- [ ] Every other PR checklist reviewed with evidence

## T14 — Dockerfile and Compose (single command)
labels: role:devops, mvp
spec: F7.4
- [ ] Multi-stage image: React built, FastAPI serves static + API
- [ ] `docker compose up` starts app + Postgres + observability + responder
- [ ] `py scripts/dev.py up|down|test` works on Windows and Linux

## T15 — Telemetry for the shopping-list journey
labels: role:backend, role:devops, mvp
spec: F7.1
- [ ] Trace, structured JSON logs with trace_id/span_id, Prometheus metrics with exemplars
- [ ] `X-Trace-Id` response header
- [ ] Redaction test: no email/password/weight/age in logs
- [ ] Collected in Tempo/Loki/Prometheus and visible in Grafana

## T16 — Alert on user impact
labels: role:devops, mvp
spec: F7.2
- [ ] `ShoppingListFailureRate` rule on non-synthetic 5xx ratio
- [ ] Alertmanager routes to the responder webhook
- [ ] Rule unit-tested with `promtool test rules`

## T17 — On-call Responder agent
labels: role:responder, mvp
spec: F7.3
- [ ] Webhook dedupes by fingerprint, ignores resolved, one run at a time
- [ ] Tool loop with allow-listed tools; playbook fallback without API key
- [ ] Probe verifies recovery; incident report written; escalation when no known cause
- [ ] Unit tests with a fake LLM client

## T18 — Fault injection and incident drill
labels: role:devops, mvp
spec: F7.3
- [ ] Flag `shopping_list_v2` reproduces a realistic 500 (`cup` unit)
- [ ] `dev.py simulate-incident` drives traffic and shows alert → responder → recovery

## T19 — CI pipeline
labels: role:devops, mvp
spec: F7.4
- [ ] PR workflow: backend unit+integration (Postgres), frontend, responder, image build, compose config

## T20 — CD, environments and rollback
labels: role:devops, mvp
spec: F7.4
- [ ] Merge to main builds `sha-<commit>` image and deploys dev
- [ ] Prod deploy waits for environment approval and uses the same tag
- [ ] Rollback workflow redeploys an earlier tag

## T21 — Public deployment
labels: role:devops, mvp
spec: F7.4
- [ ] Dev (and prod) reachable at public URLs backed by managed Postgres
- [ ] DEPLOY.md documents setup, secrets, rollback

## T22 — README and operations docs
labels: role:product, mvp
spec: all
- [ ] README: problem, features, run locally, test, architecture, deploy, demo links
- [ ] OBSERVABILITY.md and RUNBOOK.md match the real setup

## T23 — Regenerate one day and ranked swap alternatives
labels: role:backend, stretch
spec: F4.9
- [ ] Alternatives endpoint ranked by calorie fit

## T24 — PWA install and offline shopping list
labels: role:frontend, stretch
spec: F6
- [ ] Manifest + service worker caching of the last list

## T25 — Extra alerts
labels: role:devops, stretch
spec: F7.2
- [ ] Plan-generation failure rate and journey p95 latency alerts

## T26 — Telemetry for deployed environments
labels: role:devops, stretch
spec: F7.1
- [ ] OTLP export to a hosted backend (e.g. Grafana Cloud free tier)
