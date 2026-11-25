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
