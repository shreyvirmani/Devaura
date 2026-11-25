"""Phase 5 Staging Readiness, Fail-Closed Environment, Sandbox Scrubbing, and Operations Tests."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from agent.verification.runner import VerificationRunner
from apps.api.config import DEFAULT_DEV_SECRET_KEY, Settings
from apps.api.main import app
from core.jobs.retry_policy import ProviderQuotaExhaustedError
from core.jobs.worker import DurableJobWorker
from database.connection import close_db, get_database_url, get_session_maker, init_db
from database.models.incidents import Incident, IncidentSource, IncidentStatus, IncidentType, Job, JobStatus, JobType
from database.models.models import Repository


@pytest_asyncio.fixture
async def clean_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase5_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("APP_ENV", "testing")
    from apps.api.config import get_settings
    get_settings.cache_clear()
    await close_db()
    await init_db()
    yield
    await close_db()
    get_settings.cache_clear()


def test_environment_model_rejects_invalid_env():
    with pytest.raises(ValueError, match="Invalid APP_ENV"):
        Settings(APP_ENV="arbitrary_env")


def test_staging_fail_closed_validation():
    bad = Settings(
        APP_ENV="staging",
        ALLOW_DEV_USER_FALLBACK=True,
        SECRET_KEY=DEFAULT_DEV_SECRET_KEY,
        DATABASE_URL="sqlite+aiosqlite:///./devaura.db",
        ALLOWED_ORIGINS="*",
        GITHUB_APP_ID=None,
        GITHUB_APP_PRIVATE_KEY=None,
        GITHUB_WEBHOOK_SECRET=None,
    )
    errors = bad.validate_staging_or_production()
    assert len(errors) == 5
    assert any("ALLOW_DEV_USER_FALLBACK" in e for e in errors)
    assert any("SECRET_KEY" in e for e in errors)
    assert any("DATABASE_URL" in e for e in errors)
    assert any("ALLOWED_ORIGINS" in e for e in errors)
    assert any("GITHUB_APP_ID" in e for e in errors)

    good = Settings(
        APP_ENV="staging",
        ALLOW_DEV_USER_FALLBACK=False,
        SECRET_KEY="s" * 40,
        DATABASE_URL="postgresql+asyncpg://user:pass@db.example.com:5432/devaura",
        ALLOWED_ORIGINS="https://staging.devaura.dev",
        GITHUB_APP_ID="12345",
        GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----",
        GITHUB_WEBHOOK_SECRET="whsec_test_123",
    )
    assert good.validate_staging_or_production() == []


def test_postgresql_url_normalization(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/devaura")
    assert get_database_url() == "postgresql+asyncpg://user:pass@localhost:5432/devaura"


def test_sandbox_env_scrubbing(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "super-secret-jwt-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host/db")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-secret-key")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "private-key-pem")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_token")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsec_secret")

    scrubbed = VerificationRunner._build_sandbox_env()
    assert scrubbed["DEVAURA_SANDBOX"] == "1"
    for secret_var in (
        "SECRET_KEY",
        "DATABASE_URL",
        "GEMINI_API_KEY",
        "GITHUB_APP_PRIVATE_KEY",
        "GITHUB_TOKEN",
        "GITHUB_WEBHOOK_SECRET",
    ):
        assert secret_var not in scrubbed


@pytest.mark.asyncio
async def test_health_and_readiness_probes_and_no_secret_leak(clean_db, monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        live = await client.get("/api/v1/health/live")
        assert live.status_code == 200
        assert live.json()["live"] == "true"

        ready = await client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] == "true"

        # Simulate unready staging (missing PostgreSQL / GitHub App / migrations)
        monkeypatch.setenv("APP_ENV", "staging")
        monkeypatch.setenv("SECRET_KEY", "x" * 40)
        from apps.api.config import get_settings
        get_settings.cache_clear()

        unready = await client.get("/ready")
        assert unready.status_code == 503
        body = unready.json()
        assert body["ready"] == "false"
        assert "SECRET_KEY" not in str(body)
        assert "postgresql" not in str(body).lower()


@pytest.mark.asyncio
async def test_operations_endpoint_and_quota_classification(clean_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "ops@devaura.dev", "password": "Password123!", "name": "Ops User", "workspace_name": "Ops WS"},
        )
        assert signup.status_code == 201
        token = signup.json()["access_token"]
        ws_id = signup.json()["user"]["workspaces"][0]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a second workspace user to verify isolation
        signup2 = await client.post(
            "/api/v1/auth/signup",
            json={"email": "other@devaura.dev", "password": "Password123!", "name": "Other User", "workspace_name": "Other WS"},
        )
        ws2_id = signup2.json()["user"]["workspaces"][0]["id"]

        # Seed an incident + quota-exhausted job + expired-lease job
        sm = get_session_maker()
        async with sm() as db:
            repo = Repository(
                workspace_id=ws_id,
                owner="devaura-org",
                name="staging-app",
                full_name="devaura-org/staging-app",
                clone_url="https://github.com/devaura-org/staging-app.git",
                connection_status="CONNECTED",
            )
            db.add(repo)
            await db.flush()

            inc = Incident(
                workspace_id=ws_id,
                repository_id=repo.id,
                source=IncidentSource.GITHUB_WORKFLOW_RUN.value,
                dedup_key=f"{repo.id}:workflow_run:9001",
                type=IncidentType.CI_FAILURE.value,
                status=IncidentStatus.QUEUED.value,
                title="CI failed on staging-app",
            )
            db.add(inc)
            await db.flush()

            job_quota = Job(
                workspace_id=ws_id,
                incident_id=inc.id,
                job_type=JobType.INVESTIGATE_INCIDENT.value,
                status=JobStatus.QUEUED.value,
            )
            db.add(job_quota)
            await db.commit()
            job_id = job_quota.id

        # Run worker with ProviderQuotaExhaustedError -> must classify as PROVIDER_QUOTA_EXHAUSTED (not REPAIR_FAILED)
        async def _quota_investigator(incident, repo, db):
            raise ProviderQuotaExhaustedError("Gemini 429 RESOURCE_EXHAUSTED")

        worker = DurableJobWorker(investigation_runner=_quota_investigator)
        await worker.process_one()

        async with sm() as db:
            j = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
            i = (await db.execute(select(Incident).where(Incident.id == inc.id))).scalar_one()
            assert j.status == JobStatus.PROVIDER_QUOTA_EXHAUSTED.value
            assert i.status == IncidentStatus.PROVIDER_QUOTA_EXHAUSTED.value

        # Check operational visibility endpoint
        ops_resp = await client.get(f"/api/v1/workspaces/{ws_id}/operations", headers=headers)
        assert ops_resp.status_code == 200
        ops = ops_resp.json()
        assert ops["workspace_id"] == ws_id
        assert ops["jobs_summary"]["provider_quota_exhausted"] == 1
        assert len(ops["provider_failures"]) == 1
        assert len(ops["recent_incidents"]) == 1

        # Cross-workspace isolation
        forbidden = await client.get(f"/api/v1/workspaces/{ws2_id}/operations", headers=headers)
        assert forbidden.status_code == 403
