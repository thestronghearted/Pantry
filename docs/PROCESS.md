# Process

Every change travels the same path. The tracker is the source of truth for what is being worked on.

```
Issue (acceptance criteria)  →  branch  →  tests first  →  PR "Closes #N"  →  CI  →  review  →  merge to main
                                                                                         │
                                                                    CD: build image sha-<commit> → deploy dev (auto)
                                                                                         │
                                                                     manual approval → promote same tag to prod
```

## 1. Issue
- One issue per task, with **acceptance criteria as a checklist**, a role label (`role:backend`, `role:frontend`, `role:qa`, `role:devops`, `role:product`, `role:responder`) and a priority label (`mvp` or `stretch`).
- The Product/Spec agent writes or refines the issue and the matching section of `docs/SPEC.md` before implementation starts.
- `docs/tasks/BACKLOG.md` mirrors the issue list; `scripts/create_github_issues.py` publishes it.

## 2. Branch and commits
- Branch name: `<role>/issue-<N>-<slug>`, e.g. `backend/issue-7-targets`.
- Commits are small and reference the issue (`refs #7`).

## 3. Tests first
- Write or extend tests that express the acceptance criteria, watch them fail, then implement.
- Domain logic: unit tests in `backend/tests/unit`. API + DB behaviour: integration tests in `backend/tests/integration` (real Postgres). UI: Vitest + Testing Library in `frontend/tests`.

## 4. Pull request
- Body: summary, `Closes #N`, acceptance-criteria checklist ticked with evidence (test names, screenshot at 375 px for UI work), and the acting role.
- Issue comments for progress are signed `[Backend agent]`, `[Frontend agent]`, etc.

## 5. CI (every PR)
Backend unit + integration (Postgres service, Alembic upgrade), frontend tests + build, responder tests, Docker image build, `docker compose config`. A red CI blocks merge.

## 6. CD
- Merge to `main` builds the image **once**, tags it `sha-<commit>`, pushes it to GHCR.
- **Dev** deploys automatically.
- **Prod** deploys the *same tag* after a required reviewer approves the `prod` environment.
- **Rollback**: run the `rollback` workflow with a previous `sha-…` tag; see `docs/DEPLOY.md`.

## 7. Incidents
An alert wakes the Responder agent (`docs/RUNBOOK.md`). It mitigates, verifies with a synthetic probe, and writes an incident report. Unresolved incidents are escalated as a GitHub issue labelled `incident` and `needs-human`; the Product/Spec agent turns the follow-up into backlog items.

## Definition of done (all tasks)
Acceptance criteria met · tests added and green · docs/spec updated · no secrets or personal data in code or logs · PR merged with CI green.
