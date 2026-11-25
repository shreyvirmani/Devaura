"""Devaura Production Phase 2 — GitHub App Integration & Repository Onboarding Tests.

Verifies:
1. Hardened DEV_USER Fallback (Strict fail-closed in production/staging).
2. GitHub App Installation Linking & Scoping (User -> Workspace -> GitHub App).
3. Authoritative Server-Side Repository Discovery & Connection (Anti-Spoofing).
4. Webhook Ingestion Security (HMAC-SHA256, Delivery ID uniqueness, Replay-Resistance).
5. Lifecycle Propagation (installation revocation updates repository status).
6. Comprehensive Repository Health & Telemetry Detail View.
"""

import hashlib
import hmac
import json
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.auth import get_current_user
from apps.api.config import get_settings
from apps.api.main import app
from database.connection import close_db, get_session_maker, init_db
from database.models import (
    AuditEventRecord,
    GitHubAppInstallation,
    Repository,
    User,
    WebhookEventRecord,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)
from fastapi import HTTPException, Request


WEBHOOK_SECRET = "test-webhook-secret-phase2-devaura-secure-32chars"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set in-memory SQLite and testing configuration."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-phase2-verification-32chars")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    """Create initialized async test client with clean database."""
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()


def compute_signature(payload_bytes: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Compute sha256=... signature for GitHub webhook payload."""
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


async def create_workspace_and_admin(client: AsyncClient, email: str, ws_name: str):
    """Helper to register user and obtain auth headers and workspace ID."""
    res = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "Password123!",
            "name": "Test Engineer",
            "workspace_name": ws_name,
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    token = data["access_token"]
    ws_id = data["default_workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}
    return ws_id, headers, token


# -------------------------------------------------------------------------
# 1. Hardened DEV_USER Fallback Tests (Fail-Closed)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dev_user_fallback_strictly_impossible_in_production(monkeypatch):
    """Verify DEV_USER is strictly impossible in production, even if ALLOW_DEV_USER_FALLBACK=true."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "true")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(current_user=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_dev_user_fallback_strictly_impossible_in_staging(monkeypatch):
    """Verify DEV_USER is strictly impossible in staging."""
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "true")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(current_user=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_dev_user_disabled_by_default_in_development(monkeypatch):
    """Verify in development without ALLOW_DEV_USER_FALLBACK=true, request fails closed."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "false")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(current_user=None)

    assert exc_info.value.status_code == 401


# -------------------------------------------------------------------------
# 2. GitHub App Installation Linking & Scoping Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_url_requires_admin(client: AsyncClient):
    """Verify GET /install-url requires ADMIN or OWNER."""
    ws_id, admin_headers, _ = await create_workspace_and_admin(
        client, "admin1@corp.example.com", "Corp Alpha"
    )

    # Admin gets install URL
    res = await client.get(
        f"/api/v1/workspaces/{ws_id}/github/install-url",
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "install_url" in data
    assert "state" in data
    assert "github.com/apps" in data["install_url"]
    assert f"state={data['state']}" in data["install_url"]

    # Member without admin rights gets 403
    # First sign up the regular member
    member_signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "member1@corp.example.com",
            "password": "Password123!",
            "name": "Regular Member",
        },
    )
    assert member_signup.status_code == 201
    member_headers = {"Authorization": f"Bearer {member_signup.json()['access_token']}"}

    # Add regular member to workspace
    add_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "member1@corp.example.com", "role": "MEMBER"},
        headers=admin_headers,
    )
    assert add_res.status_code == 201

    member_url_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/github/install-url",
        headers=member_headers,
    )
    assert member_url_res.status_code == 403
    assert member_url_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_record_installation_and_isolation(client: AsyncClient):
    """Verify linking GitHub App installation to workspace and cross-workspace isolation."""
    ws_a, headers_a, _ = await create_workspace_and_admin(client, "admin_a@ws-a.example.com", "Workspace A")
    ws_b, headers_b, _ = await create_workspace_and_admin(client, "admin_b@ws-b.example.com", "Workspace B")

    # Workspace A links installation 12345
    inst_res = await client.post(
        f"/api/v1/workspaces/{ws_a}/github/installations",
        headers=headers_a,
        json={
            "installation_id": 12345,
            "account_name": "acme-corp",
            "account_id": 998877,
            "account_type": "Organization",
        },
    )
    assert inst_res.status_code == 201
    inst_data = inst_res.json()
    assert inst_data["installation_id"] == 12345
    assert inst_data["account_name"] == "acme-corp"
    assert inst_data["workspace_id"] == ws_a

    # Workspace B attempting to link the SAME installation receives 409 Conflict
    conflict_res = await client.post(
        f"/api/v1/workspaces/{ws_b}/github/installations",
        headers=headers_b,
        json={
            "installation_id": 12345,
            "account_name": "acme-corp",
        },
    )
    assert conflict_res.status_code == 409
    assert conflict_res.json()["error"]["code"] == "INSTALLATION_ALREADY_LINKED"

    # Listing installations for Workspace B shows empty
    list_b_res = await client.get(f"/api/v1/workspaces/{ws_b}/github/installations", headers=headers_b)
    assert list_b_res.status_code == 200
    assert len(list_b_res.json()) == 0

    # Listing installations for Workspace A shows installation 12345
    list_a_res = await client.get(f"/api/v1/workspaces/{ws_a}/github/installations", headers=headers_a)
    assert list_a_res.status_code == 200
    assert len(list_a_res.json()) == 1
    assert list_a_res.json()[0]["installation_id"] == 12345


# -------------------------------------------------------------------------
# 3. Repository Discovery & Connection Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repository_discovery_and_connect(client: AsyncClient):
    """Verify repository discovery and authoritative server-side connection."""
    ws_id, headers, _ = await create_workspace_and_admin(client, "admin@discovery.example.com", "Discovery WS")

    # Link installation 55667
    inst_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/installations",
        headers=headers,
        json={"installation_id": 55667, "account_name": "discovery-org"},
    )
    assert inst_res.status_code == 201

    # Discover repositories
    disc_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/github/installations/55667/repositories",
        headers=headers,
    )
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["total_count"] >= 1
    assert any(r["name"] == "payments-api" for r in disc_data["repositories"])

    # Connect payments-api repository
    conn_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/repositories/connect",
        headers=headers,
        json={
            "installation_id": 55667,
            "owner": "discovery-org",
            "name": "payments-api",
            "default_branch": "main",
        },
    )
    assert conn_res.status_code == 201
    repo_data = conn_res.json()
    assert repo_data["name"] == "payments-api"
    assert repo_data["connection_status"] == "CONNECTED"
    repo_id = repo_data["id"]

    # Connecting the same repository again results in 409 Conflict
    dup_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/repositories/connect",
        headers=headers,
        json={
            "installation_id": 55667,
            "owner": "discovery-org",
            "name": "payments-api",
        },
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "REPOSITORY_ALREADY_CONNECTED"

    # Detail endpoint returns complete health telemetry
    detail_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/github/repositories/{repo_id}/detail",
        headers=headers,
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["repository"]["id"] == repo_id
    assert detail["health"]["connection_status"] == "CONNECTED"
    assert detail["health"]["active_incidents_count"] == 0
    assert detail["health"]["recent_repairs_count"] == 0


# -------------------------------------------------------------------------
# 4. Webhook Ingestion & Security Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_rejects_missing_or_invalid_signature(client: AsyncClient):
    """Verify webhook rejects missing and invalid signatures with 401 Unauthorized."""
    payload = json.dumps({"zen": "Keep it logically awesome."}).encode("utf-8")

    # 1. Missing signature
    res1 = await client.post(
        "/api/v1/github/webhooks",
        content=payload,
        headers={"X-GitHub-Delivery": "del-uuid-001", "X-GitHub-Event": "ping"},
    )
    assert res1.status_code == 401
    assert res1.json()["error"]["code"] == "MISSING_SIGNATURE"

    # 2. Invalid signature
    res2 = await client.post(
        "/api/v1/github/webhooks",
        content=payload,
        headers={
            "X-GitHub-Delivery": "del-uuid-002",
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
        },
    )
    assert res2.status_code == 401
    assert res2.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_webhook_ping_and_idempotency(client: AsyncClient):
    """Verify valid webhook signature processes ping and duplicate delivery returns 200 already_processed."""
    payload_dict = {"zen": "Approachable is better than simple.", "hook_id": 999}
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(payload_bytes)
    delivery_id = "del-uuid-ping-100"

    # First delivery: processed successfully
    res1 = await client.post(
        "/api/v1/github/webhooks",
        content=payload_bytes,
        headers={
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": sig,
        },
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "pong"

    # Duplicate delivery: returns already_processed without re-mutating state
    res2 = await client.post(
        "/api/v1/github/webhooks",
        content=payload_bytes,
        headers={
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": sig,
        },
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"
    assert res2.json()["delivery_id"] == delivery_id


@pytest.mark.asyncio
async def test_webhook_repository_activity_updates_timestamp(client: AsyncClient):
    """Verify push/workflow_run webhooks update repository.last_webhook_received_at."""
    ws_id, headers, _ = await create_workspace_and_admin(client, "admin@telemetry.example.com", "Telemetry WS")

    # Link installation 77889
    await client.post(
        f"/api/v1/workspaces/{ws_id}/github/installations",
        headers=headers,
        json={"installation_id": 77889, "account_name": "telemetry-org"},
    )

    # Connect repository
    repo_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/repositories/connect",
        headers=headers,
        json={
            "installation_id": 77889,
            "owner": "telemetry-org",
            "name": "payments-api",
        },
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]

    # Send webhook push event for this repository
    webhook_payload = {
        "installation": {"id": 77889},
        "repository": {
            "id": 90123401,
            "name": "payments-api",
            "full_name": "telemetry-org/payments-api",
        },
        "ref": "refs/heads/main",
        "after": "abc1234567890",
    }
    payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    sig = compute_signature(payload_bytes)

    res = await client.post(
        "/api/v1/github/webhooks",
        content=payload_bytes,
        headers={
            "X-GitHub-Delivery": "del-uuid-push-200",
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sig,
        },
    )
    assert res.status_code == 202
    assert res.json()["status"] == "received"

    # Verify repository now has last_webhook_received_at set
    detail_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/github/repositories/{repo_id}/detail",
        headers=headers,
    )
    assert detail_res.status_code == 200
    repo_detail = detail_res.json()["repository"]
    assert repo_detail["last_webhook_received_at"] is not None


@pytest.mark.asyncio
async def test_webhook_installation_deleted_revokes_access(client: AsyncClient):
    """Verify installation deletion event marks repositories ACCESS_REVOKED."""
    ws_id, headers, _ = await create_workspace_and_admin(client, "admin@lifecycle.example.com", "Lifecycle WS")

    # Link installation 99001
    await client.post(
        f"/api/v1/workspaces/{ws_id}/github/installations",
        headers=headers,
        json={"installation_id": 99001, "account_name": "lifecycle-org"},
    )

    # Connect repository
    repo_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/repositories/connect",
        headers=headers,
        json={
            "installation_id": 99001,
            "owner": "lifecycle-org",
            "name": "payments-api",
        },
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]

    # Send installation.deleted webhook
    webhook_payload = {
        "action": "deleted",
        "installation": {"id": 99001},
    }
    payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    sig = compute_signature(payload_bytes)

    res = await client.post(
        "/api/v1/github/webhooks",
        content=payload_bytes,
        headers={
            "X-GitHub-Delivery": "del-uuid-lifecycle-300",
            "X-GitHub-Event": "installation",
            "X-Hub-Signature-256": sig,
        },
    )
    assert res.status_code == 202

    # Verify repository status changed to ACCESS_REVOKED
    detail_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/github/repositories/{repo_id}/detail",
        headers=headers,
    )
    assert detail_res.status_code == 200
    assert detail_res.json()["repository"]["connection_status"] == "ACCESS_REVOKED"


# -------------------------------------------------------------------------
# 5. Secrets Redaction & Audit Trail Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_secrets_redaction_in_audit_records(client: AsyncClient):
    """Verify secrets and tokens are never written into audit event details."""
    ws_id, headers, _ = await create_workspace_and_admin(client, "admin@audit.example.com", "Audit WS")

    # Link installation
    await client.post(
        f"/api/v1/workspaces/{ws_id}/github/installations",
        headers=headers,
        json={"installation_id": 44332, "account_name": "audit-org"},
    )

    # Inspect audit events from database directly
    session_maker = get_session_maker()
    async with session_maker() as session:
        stmt = select(AuditEventRecord).where(AuditEventRecord.workspace_id == ws_id)
        result = await session.execute(stmt)
        audits = result.scalars().all()

        assert len(audits) >= 1
        for a in audits:
            details_str = json.dumps(a.details)
            assert "PRIVATE_KEY" not in details_str
            assert "token" not in details_str.lower() or "token_type" in details_str
            assert WEBHOOK_SECRET not in details_str
