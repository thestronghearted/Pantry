# Deploying

## Pipeline
```
PR ──> CI (backend+Postgres, frontend, responder, alert rules, system start)
main ─> CI ─> build image sha-<commit> ─> GHCR ─> deploy DEV (automatic) ─> approval ─> deploy PROD (same image)
```
Workflows: [`ci.yml`](../.github/workflows/ci.yml), [`cd.yml`](../.github/workflows/cd.yml), [`rollback.yml`](../.github/workflows/rollback.yml). The deploy script is `scripts/ci/deploy.sh`: it calls the Render deploy hook with the image reference, then waits for `/ready`.

## One-time setup (done by a human; needs accounts)
1. **GitHub repo** `thestronghearted/Pantry`: public. Push `main`.
2. **Issues**: `GITHUB_TOKEN=<token with issues:write> py scripts/create_github_issues.py --apply` publishes the backlog.
3. **Image registry**: after the first CD run, GitHub → Packages → `pantry-app` → Package settings → *Change visibility → Public*, so Render can pull it without credentials.
4. **Database (Neon free tier)**: create a project with two branches, `dev` and `prod`. Copy each connection string (it ends in `?sslmode=require`).
5. **Render**: New → Blueprint → select this repo (`render.yaml`). It creates `pantry-dev` and `pantry-prod`. In each service, set `DATABASE_URL` to the matching Neon string. `SESSION_SECRET` is generated. Copy each service's **Deploy Hook URL** (Settings → Deploy Hook).
6. **GitHub environments** (Settings → Environments):
   - `dev`: secret `RENDER_DEV_DEPLOY_HOOK`, variable `DEV_URL` (for example `https://pantry-dev.onrender.com`).
   - `prod`: secret `RENDER_PROD_DEPLOY_HOOK`, variable `PROD_URL`, and **Required reviewers** (add yourself). This is the manual approval gate.
7. Merge to `main` and watch Actions: dev deploys on its own, prod waits for approval.

Settings for the deployed services are environment variables: `DATABASE_URL`, `SESSION_SECRET`, `ENVIRONMENT`, `COOKIE_SECURE=true`, `TRUST_PROXY=true`. `ADMIN_TOKEN` and `PROBE_*` are intentionally **not** set in deployed environments (admin endpoints return 404; no probe household).

## Rollback
GitHub → Actions → **Rollback** → *Run workflow* → pick `dev` or `prod` and the image tag to restore (for example `sha-1a2b3c4`, visible in the CD run summary or the Packages page). Prod still asks for approval. The workflow redeploys that image and waits for `/ready`.

Rollback is safe for the database because migrations are **backward compatible** (expand, then contract in a later release): the previous image runs against the newer schema.

## Live environments
| Environment | URL | Status |
|---|---|---|
| dev | https://pantry-dev-twxv.onrender.com (`DEV_URL`) | pending first deployment |
| prod | https://pantry-prod.onrender.com (`PROD_URL`) | pending first deployment |

> Free-tier notes: Render free web services sleep when idle (the first request after a pause takes about a minute) and share a monthly instance-hour allowance across services. Check current Render and Neon limits before relying on them; this repository does not depend on either provider's specifics beyond a Docker image and a Postgres URL.

## Local images
`docker build -t pantry-app .` builds the same image CD publishes. `docker compose up -d --build` starts the full local system.
