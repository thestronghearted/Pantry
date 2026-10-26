# AGENTS.md — Pantry Plan

Pantry Plan is a mobile-first family meal planner for weight loss. A household signs in, adds family members, and the app builds a week of meals that fits each person's calorie target, cooking-time and difficulty limits, then produces one combined shopping list.

This file is the index. Read the doc that matches your task; do not load everything.

## Where to look

| You are… | Read |
|---|---|
| Starting any task | `docs/PROCESS.md` (issue → branch → PR → CI → deploy) |
| Unsure what to build | `docs/SPEC.md` (behaviour + acceptance criteria) |
| Picking your role | `docs/AGENT_TEAM.md` (roles, inputs, outputs, definition of done) |
| Changing structure | `docs/ARCHITECTURE.md` |
| Touching logs/metrics/alerts | `docs/OBSERVABILITY.md` |
| Responding to an alert | `docs/RUNBOOK.md` |
| Deploying / rolling back | `docs/DEPLOY.md` |
| Looking for work | GitHub Issues (mirrored in `docs/tasks/BACKLOG.md`) |

## Stack
FastAPI + SQLAlchemy + Alembic (Postgres) · React (Vite) served by FastAPI · OpenTelemetry → Collector → Tempo/Loki, Prometheus, Grafana · Responder agent (`responder/`) · GitHub Actions → GHCR → Render.

## Commands (run from repo root)
- `py scripts/dev.py up` / `down` — whole system in Docker Compose (app on :8080, Grafana on :3001)
- `py scripts/dev.py test` — all tests (starts a throwaway Postgres; needs Docker running)
- `py scripts/dev.py simulate-incident` — inject the bad release and watch the responder
- Backend only: `cd backend && py -m pytest tests/unit`
- Frontend only: `cd frontend && npm test`

## Rules every agent follows
1. Work from an issue; branch `role/issue-N-slug`; PR body contains `Closes #N`; sign issue comments `[Role agent]`.
2. Spec before code: if behaviour is not in `docs/SPEC.md`, update the spec in the same PR.
3. Business rules live in `backend/app/domain/` as pure functions with unit tests. No DB access there.
4. Every query is scoped by `household_id`. Never return another household's data.
5. Never log emails, passwords, cookies, weight, age, or request bodies. Log opaque ids and counts only.
6. Migrations are backward-compatible (expand/contract) so image rollback is safe.
7. Never commit secrets. `.env` is git-ignored; `.env.example` holds placeholders only.
8. Nutrition and calorie output is an estimate, not medical advice; keep the notices in the UI.
