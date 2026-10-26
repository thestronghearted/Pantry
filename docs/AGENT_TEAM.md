# Agent team

Pantry Plan is built by a small team of role-specialised agents. In practice one Claude Code session plays each role in turn, and each role has its own scope, inputs, outputs and definition of done. Roles are recorded on every issue, PR and comment (`[Backend agent]`), so a reviewer can follow who did what.

| Role | Scope | Reads | Produces | Done when |
|---|---|---|---|---|
| **Product/Spec agent** | Problem, behaviour, acceptance criteria, backlog | User requests, incident reports | `docs/SPEC.md`, issues with checklists | Every MVP behaviour has testable criteria and an issue |
| **Backend agent** | `backend/`: domain logic, API, DB, migrations, telemetry hooks | Issue, SPEC | Code + unit/integration tests | Criteria pass in CI; domain stays pure; queries household-scoped |
| **Frontend agent** | `frontend/`: mobile-first UI | Issue, SPEC, API shapes | Pages, components, component tests | Works at 375 px, tests pass, shows trace id footer |
| **QA agent** | Cross-cutting verification | SPEC, PRs | Edge-case tests (macros never negative, portions 0.5–2.0, isolation), review comments | Every PR checklist item has evidence; isolation test green |
| **DevOps/SRE agent** | Docker, Compose, CI/CD, hosting, observability stack, alert rules | Issue, OBSERVABILITY, DEPLOY | Dockerfiles, workflows, Prometheus/Grafana config | One-command local start; CI green; deploy + rollback proven |
| **On-call Responder agent** (runtime) | `responder/`: wakes on alerts | Alertmanager webhook, Prometheus, Loki, feature flags | Mitigation, verification, incident report or escalation | Alert clears and probe passes, or a `needs-human` issue exists |

## Handoffs
1. Product/Spec → Backend and Frontend: an issue whose checklist is the contract. API shape is agreed in the issue before either side codes.
2. Backend → Frontend: endpoint merged and documented in `docs/ARCHITECTURE.md` first; Frontend builds against it.
3. Backend/Frontend → QA: PR opened with tests; QA adds edge cases and reviews against the SPEC.
4. QA → DevOps: green CI on `main` triggers CD.
5. Responder → Product/Spec: incident report becomes backlog items so the root cause gets a permanent fix.

## Working agreements
- Smallest useful PR; one issue each.
- A role does not edit another role's files without a comment on the issue (exception: tests that expose a bug).
- Human decisions (accounts, secrets, production approvals, medical-sensitive wording) stay with the user; agents ask rather than assume.

## The runtime agent
The Responder is the only agent that runs in production-like conditions. It has a fixed, allow-listed toolset and cannot change code, only flip known feature flags, run probes, write reports and escalate. Details: `docs/RUNBOOK.md`.
