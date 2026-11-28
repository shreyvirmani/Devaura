"""Devaura Local Production Readiness & Multi-User Workspace Isolation Tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from apps.api.config import DEFAULT_DEV_SECRET_KEY, Settings, get_settings
from apps.api.main import app
from database.connection import close_db, init_db


@pytest_asyncio.fixture
async def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "local_prod_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "false")
    get_settings.cache_clear()
    await close_db()
    await init_db()
    yield
    await close_db()
    get_settings.cache_clear()


def test_local_production_mode_fail_closed_validation():
    bad = Settings(
        APP_ENV="local_production",
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

    good = Settings(
        APP_ENV="local_production",
        ALLOW_DEV_USER_FALLBACK=False,
        SECRET_KEY="x" * 48,
        DATABASE_URL="postgresql+asyncpg://devaura:pass@localhost:5432/devaura",
        ALLOWED_ORIGINS="http://localhost:3000",
        GITHUB_APP_ID="12345",
        GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nplaceholder\n-----END RSA PRIVATE KEY-----",
        GITHUB_WEBHOOK_SECRET="whsec_local_prod_123",
    )
    assert good.validate_staging_or_production() == []


@pytest.mark.asyncio
async def test_local_production_blocks_dev_fallback_and_expired_jwt(isolated_db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "local_production")
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "true")
    monkeypatch.setenv("SECRET_KEY", "s" * 40)
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated requests must fail closed even if ALLOW_DEV_USER_FALLBACK=true
        r_repos = await client.get("/api/v1/repositories")
        assert r_repos.status_code == 401

        r_ci = await client.get("/api/v1/code-intelligence/status/some-repo")
        assert r_ci.status_code == 401

        # Expired JWT must be rejected
        expired_token = jwt.encode(
            {"sub": "u1", "email": "u1@devaura.dev", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
            "s" * 40,
            algorithm="HS256",
        )
        r_exp = await client.get(
            "/api/v1/repositories",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert r_exp.status_code == 401


@pytest.mark.asyncio
async def test_multi_user_complete_cross_workspace_isolation(isolated_db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "local_production")
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "false")
    monkeypatch.setenv("SECRET_KEY", "z" * 40)
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User A signup
        sa = await client.post(
            "/api/v1/auth/signup",
            json={"email": "alice@devaura.dev", "password": "Password123!", "name": "Alice", "workspace_name": "Alice WS"},
        )
        assert sa.status_code == 201
        # Verify secure, httponly cookie attributes in local_production
        set_cookie = sa.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie
        assert "secure" in set_cookie
        token_a = sa.json()["access_token"]
        ws_a = sa.json()["user"]["workspaces"][0]["id"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # User B signup
        sb = await client.post(
            "/api/v1/auth/signup",
            json={"email": "bob@devaura.dev", "password": "Password123!", "name": "Bob", "workspace_name": "Bob WS"},
        )
        assert sb.status_code == 201
        token_b = sb.json()["access_token"]
        ws_b = sb.json()["user"]["workspaces"][0]["id"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Alice creates Repo A & Investigation A
        repo_a = await client.post(
            "/api/v1/repositories",
            json={
                "owner": "alice-org",
                "name": "service-a",
                "clone_url": "https://github.com/alice-org/service-a.git",
                "workspace_id": ws_a,
            },
            headers=headers_a,
        )
        assert repo_a.status_code == 201
        repo_a_id = repo_a.json()["id"]

        inv_a = await client.post(
            "/api/v1/investigations",
            json={"repository_id": repo_a_id, "title": "Alice Secret Failure"},
            headers=headers_a,
        )
        assert inv_a.status_code == 201
        inv_a_id = inv_a.json()["id"]

        # Bob cannot list Alice's repository or investigation
        assert (await client.get("/api/v1/repositories", headers=headers_b)).json() == []
        assert (await client.get("/api/v1/investigations", headers=headers_b)).json() == []

        # Bob cannot read or mutate Alice's resources by ID
        assert (await client.get(f"/api/v1/repositories/{repo_a_id}", headers=headers_b)).status_code == 403
        assert (
            await client.post(
                "/api/v1/repositories",
                json={
                    "owner": "bob-org",
                    "name": "hijack",
                    "clone_url": "https://github.com/bob-org/hijack.git",
                    "workspace_id": ws_a,
                },
                headers=headers_b,
            )
        ).status_code == 403
        assert (await client.get(f"/api/v1/investigations/{inv_a_id}", headers=headers_b)).status_code == 403
        assert (await client.post(f"/api/v1/investigations/{inv_a_id}/run", headers=headers_b)).status_code == 403
        assert (await client.get(f"/api/v1/investigations/{inv_a_id}/evidence", headers=headers_b)).status_code == 403
        assert (await client.get(f"/api/v1/investigations/{inv_a_id}/candidates", headers=headers_b)).status_code == 403
        assert (await client.get(f"/api/v1/investigations/{inv_a_id}/timeline", headers=headers_b)).status_code == 403
        assert (
            await client.post(
                "/api/v1/investigations",
                json={"repository_id": repo_a_id, "title": "Cross-tenant"},
                headers=headers_b,
            )
        ).status_code == 403

        # Bob cannot access Alice's workspace endpoints
        assert (await client.get(f"/api/v1/workspaces/{ws_a}", headers=headers_b)).status_code == 403
        assert (await client.get(f"/api/v1/workspaces/{ws_a}/incidents", headers=headers_b)).status_code == 403
        assert (await client.get(f"/api/v1/workspaces/{ws_a}/jobs", headers=headers_b)).status_code == 403
        assert (await client.get(f"/api/v1/workspaces/{ws_a}/operations", headers=headers_b)).status_code == 403
        assert (await client.get(f"/api/v1/workspaces/{ws_b}/operations", headers=headers_b)).status_code == 200


def test_fresh_process_imports_api_worker_and_mcp():
    for stmt in (
        "import apps.api.main; print('API_OK')",
        "import apps.worker.main; print('WORKER_OK')",
        "from mcp.server.devaura_server import get_native_mcp_server; s = get_native_mcp_server(); print('MCP_OK')",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", stmt],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
