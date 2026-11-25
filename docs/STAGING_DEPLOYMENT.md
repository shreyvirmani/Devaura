# Devaura Staging Deployment, Migration & Rollback Guide

## 1. Process Architecture

Devaura staging runs four independent components:

1. **Database**: Hosted PostgreSQL 16 (`DATABASE_URL=postgresql+asyncpg://...`)
2. **API Server**: FastAPI (`uvicorn apps.api.main:app --host 0.0.0.0 --port 8000`) with `WORKER_ENABLED=false`
3. **Durable Worker**: Independent worker process (`python -m apps.worker.main`)
4. **Frontend**: Next.js (`npm --prefix apps/web run build && npm --prefix apps/web run start`)

Docker Compose reference: [docker-compose.yml](../docker-compose.yml).

---

## 2. Required Staging Environment Variables

Staging (`APP_ENV=staging`) fails closed on startup if any of these are missing or insecure:

- `APP_ENV=staging`
- `ALLOW_DEV_USER_FALLBACK=false`
- `SECRET_KEY=<32+ char random secret>`
- `DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<db>`
- `ALLOWED_ORIGINS=https://<staging-frontend-domain>` (no `*`)
- `GITHUB_APP_ID=<app-id>`
- `GITHUB_APP_PRIVATE_KEY=<pem-private-key>`
- `GITHUB_WEBHOOK_SECRET=<webhook-secret>`
- `GEMINI_API_KEY=<provider-api-key>`
- `WORKER_ENABLED=false` (on the API service)

Frontend build/runtime environment variables (public only — never place server secrets here):
- `NEXT_PUBLIC_API_URL=https://<staging-api-domain>`
- `NEXT_PUBLIC_APP_ENV=staging`

---

## 3. GitHub App Minimum Permissions & Webhook Setup

- **Permissions:**
  - Repository Contents: Read & Write (create repair branch & commit)
  - Pull Requests: Read & Write (open PRs; never auto-merge)
  - Checks / Actions: Read-only (inspect CI failure metadata)
  - Metadata: Read-only
- **Webhook URL:** `https://<staging-api-domain>/api/v1/github/webhooks`
- **Webhook Events:** `workflow_run`, `check_run`, `pull_request`, `push`, `installation`, `installation_repositories`

---

## 4. Database Migration & Rollback

### Forward Migration (Clean or Existing DB)
```bash
alembic upgrade head
```
Expected head revision: `0004_phase4_repair_pipeline`.

### Health & Readiness Verification
- Liveness: `GET /health/live` or `GET /api/v1/health/live` -> HTTP `200`
- Readiness: `GET /ready` or `GET /api/v1/health/ready` -> HTTP `200` (returns `503` if DB, Alembic head, or GitHub App config is unavailable)

### Rollback Strategy
- **Never** automatically run `alembic downgrade` in staging/production.
- For application regressions, roll back the API and Worker container images/processes to the previous commit while keeping forward-compatible DB schema, or restore from a PostgreSQL point-in-time snapshot taken prior to migration.

---

## 5. Phase 6 Single-Stack Blueprint (`render.yaml`) & Manual Provisioning Steps

Chosen hosting stack: **Render** ([render.yaml](../render.yaml)) — Managed PostgreSQL (`devaura-staging-db`), FastAPI API (`devaura-staging-api`), independent Worker (`devaura-staging-worker`), and Next.js Web (`devaura-staging-web`).

### Manual Steps Requiring External Credentials (Blocked in Local Environment)
1. **Provision Stack:** Connect the repository in Render using `render.yaml` (or deploy PostgreSQL + API + Worker + Web services).
2. **Set Unsynced Secrets:** Populate `ALLOWED_ORIGINS`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, `GEMINI_API_KEY`, and `NEXT_PUBLIC_API_URL` in the Render dashboard.
3. **Verify Health/Readiness:** Run `python scripts/verify_staging_readiness.py --api-url https://<staging-api-url>`.
4. **Create Disposable Staging Repo:** Create `devaura-staging-e2e` on GitHub with a failing pytest + GitHub Actions workflow, install the staging GitHub App on that repo only, and point the GitHub App webhook to `https://<staging-api-url>/api/v1/github/webhooks`.
5. **Execute Live E2E:** Push a controlled defect to trigger GitHub Actions failure -> webhook -> incident -> investigation -> repair -> sandbox verification -> UI `Approve & Create PR` -> verify real branch, commit, and PR on GitHub (without merging).

---

## 6. Zero-Cost Staging (`FREE STAGING ONLY` — No Card / No Paid Services)

### Architecture Comparison

- **PRODUCTION ARCHITECTURE:** Managed PostgreSQL + FastAPI Web Service + Dedicated Background Worker + Next.js Web Service.
- **ZERO-COST STAGING ARCHITECTURE (`render.yaml` + Supabase + Vercel Hobby):**
  - `render.yaml` is the current **zero-cost staging deployment configuration**.
  - **Frontend:** Vercel Hobby (`NEXT_PUBLIC_API_URL=<Render API URL>`, `NEXT_PUBLIC_APP_ENV=staging`)
  - **API:** Render Free Web Service (`devaura-staging-api`, `WORKER_ENABLED=false`, `startCommand: python scripts/start_free_staging_api.py`)
  - **Worker:** Render Free Web Service (`devaura-staging-worker`, `python -m apps.worker.main`, `FREE_STAGING_HTTP_HEALTH=true` exposing `/healthz`)
  - **Database:** External Supabase Free PostgreSQL (`DATABASE_URL=postgresql+asyncpg://...`)

### Render Free-Tier Startup Migration Workaround
- Render Free Web Services do not support `preDeployCommand`.
- Therefore, zero-cost staging performs `alembic upgrade head` during API process startup via [scripts/start_free_staging_api.py](../scripts/start_free_staging_api.py).
- **Startup migration must succeed before the API starts serving traffic**; if `alembic upgrade head` fails, the API process aborts immediately without starting Uvicorn.
- The Worker does **not** run Alembic migrations on startup, preventing concurrent migration race conditions.
- This is a staging-only deployment adaptation; Devaura's production architecture (independent durable Worker + PostgreSQL-backed job system + Alembic) is unchanged.

### Manual Zero-Cost Provisioning Steps
1. Create a free PostgreSQL database in **Supabase** and copy its PostgreSQL connection string (`postgresql+asyncpg://...`).
2. Deploy [render.yaml](../render.yaml) in **Render** (two Free Web Services only — no Render Postgres, no paid Background Worker, no `preDeployCommand`).
3. Set `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS` (your Vercel URL), `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, and `GEMINI_API_KEY` on both Render services.
4. Deploy `apps/web` to **Vercel Hobby** with `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_APP_ENV=staging`.
5. Run `python scripts/verify_staging_readiness.py --api-url https://<devaura-staging-api>.onrender.com`.

### Free-Staging Limitations (Mandatory Disclosure)
1. **Render free services can sleep** after inactivity (cold-start latency and paused worker polling while sleeping).
2. **Supabase free database has resource limits** (connection & storage caps).
3. **Render's paid Background Worker is not used.**
4. **The Worker is deployed through an isolated free Web Service HTTP health adapter** (`FREE_STAGING_HTTP_HEALTH=true` in `apps/worker/main.py`).
5. **This configuration is NOT the intended production infrastructure.**
6. **No production SLA is implied.**
7. **No production readiness claim may be made from this environment.**


