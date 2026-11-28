# Devaura — Local Production Self-Hosting Guide (`APP_ENV=local_production`)

This guide runs Devaura locally with **full production security boundaries**: fail-closed authentication, PostgreSQL + Alembic migrations, independent `DurableJobWorker`, workspace isolation, and GitHub App validation.

---

## 1. Install Dependencies
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r apps/api/requirements.txt
npm --prefix apps/web ci
```

## 2. Configure Environment
Copy `.env.example` to `.env` and set real values (never commit `.env`):
- `APP_ENV=local_production`
- `ALLOW_DEV_USER_FALLBACK=false`
- `SECRET_KEY=<32+ character random secret>`
- `DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db>`
- `ALLOWED_ORIGINS=http://localhost:3000`
- `WORKER_ENABLED=false`
- `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`
- `GEMINI_API_KEY=<provider key>`

## 3. Start PostgreSQL
Ensure a local PostgreSQL 16 instance is running and the target database exists.

## 4. Run Alembic Migrations (Sole Schema Authority)
```bash
alembic upgrade head
```
Expected revision chain: `0000_initial_core_schema -> 0001_saas_foundation -> 0002_github_app_integration -> 0003_incidents_and_jobs -> 0004_phase4_repair_pipeline (head)`.

## 5. Start API, Worker & Frontend (Separate Processes)
Terminal 1 (API):
```bash
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```
Terminal 2 (Independent Durable Worker):
```bash
python -m apps.worker.main
```
Terminal 3 (Frontend):
```bash
npm --prefix apps/web run build
npm --prefix apps/web run start
```

Verify readiness before use:
- Liveness: `GET http://127.0.0.1:8000/api/v1/health/live` -> `200`
- Readiness: `GET http://127.0.0.1:8000/api/v1/health/ready` -> `200` (returns `503` if PostgreSQL, Alembic head, or GitHub App config is invalid)

## 6. Bootstrap First User & Workspace
Open `http://localhost:3000/signup` (or `POST /api/v1/auth/signup`) to create the first user and initial `OWNER` workspace. No default admin user is seeded automatically.

## 7. GitHub App & Optional Local Webhook Tunnel
- Configure your GitHub App with `Repository Contents (R/W)`, `Pull Requests (R/W)`, `Checks/Actions (Read)`, and `Metadata (Read)`.
- To receive live GitHub webhooks locally, expose port `8000` via an HTTPS tunnel (e.g. Cloudflare Tunnel or ngrok) and set the GitHub App webhook URL to `https://<tunnel-host>/api/v1/github/webhooks`.
- Without a tunnel, the API, Worker, Frontend, Auth, Workspaces, and Code Intelligence operate normally; you just will not receive external GitHub webhook pushes.
