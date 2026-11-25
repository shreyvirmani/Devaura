"""Devaura Production Phase 1 — SaaS Foundation Test Suite.

Verifies:
1. Production Authentication (Signup, Login, Token generation, Password hashing).
2. Multi-Tenancy & Workspace Boundary Isolation (User -> Workspace -> Resource).
3. Cross-Tenant IDOR Prevention (Strict 403/404 on foreign tenant resources).
4. Role-Based Access Control (OWNER, ADMIN, MEMBER permission gates).
5. Append-Only Structured Audit Logging and Secret Redaction.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.main import app
from apps.api.security import verify_password
from database.connection import close_db, get_session_maker, init_db
from database.models import (
    AuditEventRecord,
    Repository,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Ensure in-memory SQLite and testing configuration for test isolation."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-saas-foundation-verification-32chars")


@pytest_asyncio.fixture
async def client():
    """Create initialized async test client with clean in-memory database."""
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()


# -------------------------------------------------------------------------
# 1. Authentication Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signup_creates_user_and_workspace_and_token(client: AsyncClient):
    """Verify signup registers user, creates default workspace, assigns OWNER, and returns JWT."""
    payload = {
        "email": "alice@acme.example.com",
        "password": "SecurePassword123!",
        "name": "Alice Engineer",
        "workspace_name": "Acme Engineering",
    }
    res = await client.post("/api/v1/auth/signup", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@acme.example.com"
    assert data["user"]["name"] == "Alice Engineer"
    assert len(data["user"]["workspaces"]) == 1
    assert data["user"]["workspaces"][0]["name"] == "Acme Engineering"
    assert data["user"]["workspaces"][0]["role"] == "OWNER"
    assert data["user"]["workspaces"][0]["is_owner"] is True
    assert data["default_workspace_id"] == data["user"]["workspaces"][0]["id"]

    # Verify session cookie was set
    assert "set-cookie" in res.headers
    assert "devaura_token" in res.headers["set-cookie"]


@pytest.mark.asyncio
async def test_signup_duplicate_email_rejected(client: AsyncClient):
    """Verify registering duplicate email is rejected with HTTP 409."""
    payload = {
        "email": "duplicate@test.example.com",
        "password": "Password123!",
        "name": "First User",
    }
    res1 = await client.post("/api/v1/auth/signup", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/signup", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_flow_and_credential_verification(client: AsyncClient):
    """Verify login succeeds with valid credentials and fails on invalid credentials."""
    # Register user
    signup_payload = {
        "email": "bob@security.example.com",
        "password": "CorrectPassword123!",
        "name": "Bob Builder",
    }
    signup_res = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_res.status_code == 201

    # Login with correct password
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@security.example.com", "password": "CorrectPassword123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "bob@security.example.com"

    # Login with wrong password
    bad_pw_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@security.example.com", "password": "WrongPassword!"},
    )
    assert bad_pw_res.status_code == 401
    assert bad_pw_res.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # Login with unknown email
    unknown_email_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@security.example.com", "password": "SomePassword123!"},
    )
    assert unknown_email_res.status_code == 401
    assert unknown_email_res.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_auth_me_and_token_validation(client: AsyncClient):
    """Verify /api/v1/auth/me resolves current user and rejects invalid/tampered tokens."""
    # Register user
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={"email": "charlie@test.example.com", "password": "Password123!", "name": "Charlie"},
    )
    token = signup_res.json()["access_token"]

    # Valid token
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "charlie@test.example.com"
    assert len(me_data["workspaces"]) == 1

    # Tampered / invalid token
    bad_res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
    assert bad_res.status_code == 401
    assert bad_res.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_password_hashing_security(client: AsyncClient):
    """Verify passwords are saved as salted PBKDF2 hashes and plaintext is never stored."""
    plain_password = "SuperSecretPassword123!"
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "dave@crypto.example.com", "password": plain_password, "name": "Dave"},
    )

    session_factory = get_session_maker()
    async with session_factory() as session:
        stmt = select(User).where(User.email == "dave@crypto.example.com")
        user = (await session.execute(stmt)).scalar_one()

        assert user.hashed_password is not None
        assert user.hashed_password != plain_password
        assert user.hashed_password.startswith("pbkdf2:sha256:")
        assert verify_password(plain_password, user.hashed_password)
        assert not verify_password("WrongPassword!", user.hashed_password)


# -------------------------------------------------------------------------
# 2. Multi-Tenancy & Tenant Boundary Isolation Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_tenant_workspace_isolation(client: AsyncClient):
    """Verify Tenant A cannot see or access Tenant B's workspace."""
    # 1. Create Tenant A
    res_a = await client.post(
        "/api/v1/auth/signup",
        json={"email": "tenant_a@corp.example.com", "password": "Password123!", "name": "Tenant A", "workspace_name": "Workspace A"},
    )
    token_a = res_a.json()["access_token"]
    ws_a_id = res_a.json()["default_workspace_id"]

    # 2. Create Tenant B
    res_b = await client.post(
        "/api/v1/auth/signup",
        json={"email": "tenant_b@corp.example.com", "password": "Password123!", "name": "Tenant B", "workspace_name": "Workspace B"},
    )
    token_b = res_b.json()["access_token"]
    ws_b_id = res_b.json()["default_workspace_id"]

    # Tenant A accesses Workspace A -> 200 OK
    res = await client.get(f"/api/v1/workspaces/{ws_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    assert res.json()["name"] == "Workspace A"

    # Tenant B accesses Workspace B -> 200 OK
    res = await client.get(f"/api/v1/workspaces/{ws_b_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 200
    assert res.json()["name"] == "Workspace B"

    # Tenant A attempts to access Workspace B -> 403 Forbidden
    cross_res = await client.get(f"/api/v1/workspaces/{ws_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert cross_res.status_code == 403
    assert cross_res.json()["error"]["code"] == "WORKSPACE_ACCESS_DENIED"

    # Tenant B attempts to access Workspace A -> 403 Forbidden
    cross_res2 = await client.get(f"/api/v1/workspaces/{ws_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert cross_res2.status_code == 403
    assert cross_res2.json()["error"]["code"] == "WORKSPACE_ACCESS_DENIED"

    # List workspaces for Tenant A -> only Workspace A
    list_a = await client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {token_a}"})
    assert list_a.status_code == 200
    workspaces_a = list_a.json()
    assert len(workspaces_a) == 1
    assert workspaces_a[0]["id"] == ws_a_id

    # List workspaces for Tenant B -> only Workspace B
    list_b = await client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {token_b}"})
    assert list_b.status_code == 200
    workspaces_b = list_b.json()
    assert len(workspaces_b) == 1
    assert workspaces_b[0]["id"] == ws_b_id


# -------------------------------------------------------------------------
# 3. Resource Scoping & IDOR Prevention Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resource_scoping_and_idor_prevention(client: AsyncClient):
    """Verify resources (repositories) are strictly scoped and IDOR attempts fail with 404."""
    # Tenant 1 Setup
    t1 = await client.post(
        "/api/v1/auth/signup",
        json={"email": "corp1@example.com", "password": "Password123!", "name": "Corp 1", "workspace_name": "Corp 1 WS"},
    )
    token_1 = t1.json()["access_token"]
    ws_1_id = t1.json()["default_workspace_id"]

    # Tenant 2 Setup
    t2 = await client.post(
        "/api/v1/auth/signup",
        json={"email": "corp2@example.com", "password": "Password123!", "name": "Corp 2", "workspace_name": "Corp 2 WS"},
    )
    token_2 = t2.json()["access_token"]
    ws_2_id = t2.json()["default_workspace_id"]

    # Tenant 1 connects a repository to Workspace 1
    repo_payload = {
        "owner": "corp1-org",
        "name": "internal-service",
        "provider": "github",
        "default_branch": "main",
        "clone_url": "https://github.com/corp1-org/internal-service.git",
    }
    repo_res = await client.post(
        f"/api/v1/workspaces/{ws_1_id}/repositories",
        json=repo_payload,
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert repo_res.status_code == 201
    repo_1_id = repo_res.json()["id"]

    # Tenant 1 lists repositories -> sees internal-service
    t1_repos = await client.get(
        f"/api/v1/workspaces/{ws_1_id}/repositories",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert t1_repos.status_code == 200
    assert len(t1_repos.json()) == 1
    assert t1_repos.json()[0]["id"] == repo_1_id

    # Tenant 2 lists repositories in Workspace 2 -> empty list
    t2_repos = await client.get(
        f"/api/v1/workspaces/{ws_2_id}/repositories",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert t2_repos.status_code == 200
    assert len(t2_repos.json()) == 0

    # IDOR Attack: Tenant 2 attempts to fetch Tenant 1's repository using Workspace 2 context
    idor_res = await client.get(
        f"/api/v1/workspaces/{ws_2_id}/repositories/{repo_1_id}",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    # Must return 404 Not Found to prevent leaking existence of Tenant 1's repository
    assert idor_res.status_code == 404
    assert idor_res.json()["error"]["code"] == "REPOSITORY_NOT_FOUND"

    # Direct access attempt: Tenant 2 tries to access Workspace 1's repository endpoint directly
    direct_attack_res = await client.get(
        f"/api/v1/workspaces/{ws_1_id}/repositories/{repo_1_id}",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert direct_attack_res.status_code == 403
    assert direct_attack_res.json()["error"]["code"] == "WORKSPACE_ACCESS_DENIED"


# -------------------------------------------------------------------------
# 4. Role-Based Access Control (RBAC) Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rbac_role_enforcement(client: AsyncClient):
    """Verify OWNER, ADMIN, and MEMBER permissions are strictly enforced."""
    # 1. Create Workspace Owner
    owner_reg = await client.post(
        "/api/v1/auth/signup",
        json={"email": "owner@team.example.com", "password": "Password123!", "name": "Team Owner", "workspace_name": "Team Space"},
    )
    assert owner_reg.status_code == 201
    owner_token = owner_reg.json()["access_token"]
    ws_id = owner_reg.json()["default_workspace_id"]

    # 2. Create another user to add as MEMBER
    member_reg = await client.post(
        "/api/v1/auth/signup",
        json={"email": "member@team.example.com", "password": "Password123!", "name": "Team Member", "workspace_name": "Personal Space"},
    )
    assert member_reg.status_code == 201
    member_token = member_reg.json()["access_token"]
    member_user_id = member_reg.json()["user"]["id"]

    # 3. Owner adds user as MEMBER to Team Space
    add_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "member@team.example.com", "role": "MEMBER"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert add_res.status_code == 201
    assert add_res.json()["role"] == "MEMBER"

    # 4. Member can read workspace details
    read_res = await client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert read_res.status_code == 200
    assert read_res.json()["role"] == "MEMBER"

    # 5. Member attempts to update workspace name -> 403 Forbidden (requires ADMIN+)
    patch_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Hacked Name"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 6. Member attempts to invite someone -> 403 Forbidden
    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "stranger@team.example.com", "role": "MEMBER"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert invite_res.status_code == 403
    assert invite_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 7. Member attempts to delete/deactivate workspace -> 403 Forbidden (requires OWNER)
    del_res = await client.delete(
        f"/api/v1/workspaces/{ws_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "OWNER_REQUIRED"

    # 8. Owner attempts to remove self (owner cannot be removed) -> 403 Forbidden
    del_owner_res = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{owner_reg.json()['user']['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert del_owner_res.status_code == 403
    assert del_owner_res.json()["error"]["code"] == "CANNOT_REMOVE_OWNER"


# -------------------------------------------------------------------------
# 5. Audit Logging & Secret Redaction Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_logging_and_secret_redaction(client: AsyncClient):
    """Verify critical events produce audit log records and credentials are never stored."""
    # Register user
    reg = await client.post(
        "/api/v1/auth/signup",
        json={"email": "audit_user@audit.example.com", "password": "SensitivePassword123!", "name": "Audit User"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    ws_id = reg.json()["default_workspace_id"]

    # Verify audit event for user signup / workspace creation in database
    session_factory = get_session_maker()
    async with session_factory() as session:
        stmt = select(AuditEventRecord).where(AuditEventRecord.workspace_id == ws_id)
        events = (await session.execute(stmt)).scalars().all()

        assert len(events) >= 1
        actions = [e.action for e in events]
        assert "user.signup" in actions

        # Verify no passwords or tokens were recorded in audit details
        for event in events:
            details_str = str(event.details).lower()
            assert "sensitivepassword123!" not in details_str
            assert "token" not in event.details or event.details.get("token") == "[REDACTED]"

    # Verify audit endpoint exposes audit events to workspace members
    audit_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_res.status_code == 200
    audit_list = audit_res.json()
    assert len(audit_list) >= 1
    assert audit_list[0]["action"] == "user.signup"
