"""Devaura Phase 7 Pull Request REST API Integration Tests.

Validates the complete verified repair to GitHub Pull Request pipeline through FastAPI routes:
1. POST /api/v1/repairs/{id}/pr/prepare
2. GET  /api/v1/repairs/{id}/pr/context
3. POST /api/v1/repairs/{id}/pr/approve (with agent self-approval denial)
4. POST /api/v1/repairs/{id}/pr/reject
5. POST /api/v1/repairs/{id}/pr/create
6. GET  /api/v1/repairs/{id}/pr
7. GET  /api/v1/repairs/{id}/pr/status
8. GET  /api/v1/repairs/{id}/pr/history
9. GET  /api/v1/pull-requests
"""

import os
import shutil
import tempfile
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from database.connection import close_db, init_db


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from agent.pr.git_manager import GitStateManager
    monkeypatch.setattr(GitStateManager, "validate_working_tree_clean", lambda self, allowed_files: (True, None))


@pytest_asyncio.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()


@pytest_asyncio.fixture
async def verified_repair(client: AsyncClient):
    """Fixture that initializes repo, investigation, repair, plan, patch, approval, application, and passes verification."""
    # 1. Repo
    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "owner": "shreyvirmani",
            "name": "Devaura",
            "clone_url": "https://github.com/shreyvirmani/Devaura.git",
            "default_branch": "main",
        },
    )
    repo = repo_res.json()

    # 2. Investigation
    inv_res = await client.post(
        "/api/v1/investigations",
        json={
            "repository_id": repo["id"],
            "failure_description": "IndexError in auth.py get_current_user",
            "issue_title": "Fix token header index",
            "error_type": "IndexError",
            "error_message": "IndexError: list index out of range",
            "stack_trace": 'File "apps/api/auth.py", line 28, in get_current_user\n    token = authorization.split()[1]',
        },
    )
    inv = inv_res.json()
    inv_id = inv["id"]

    run_res = await client.post(f"/api/v1/investigations/{inv_id}/run")
    assert run_res.status_code == 200

    # 3. Repair
    rep_res = await client.post("/api/v1/repairs", json={"investigation_id": inv_id})
    repair = rep_res.json()
    repair_id = repair["id"]

    # 4. Context, Plan, Patch
    await client.post(f"/api/v1/repairs/{repair_id}/context")
    await client.post(f"/api/v1/repairs/{repair_id}/plan")
    patch_res = await client.post(f"/api/v1/repairs/{repair_id}/patch")
    patch_hash = patch_res.json()["patch"]["patch_hash"]

    # 5. Phase 5 Approval & Application
    await client.post(f"/api/v1/repairs/{repair_id}/approve", json={"patch_hash": patch_hash})
    await client.post(f"/api/v1/repairs/{repair_id}/apply")

    # 6. Phase 6 Verification -> VERIFIED
    verify_res = await client.post(
        f"/api/v1/repairs/{repair_id}/verify",
        json={
            "custom_commands": {
                "tests": 'python -c "exit(0)"',
                "lint": 'python -c "exit(0)"',
                "typecheck": 'python -c "exit(0)"',
            }
        },
    )
    assert verify_res.status_code == 200
    verified_data = verify_res.json()["repair"]
    assert verified_data["status"] == "VERIFIED"

    return verified_data


@pytest.mark.asyncio
async def test_pr_full_orchestration_flow(client: AsyncClient, verified_repair):
    repair_id = verified_repair["id"]

    # 1. Prepare PR
    prep_res = await client.post(
        f"/api/v1/repairs/{repair_id}/pr/prepare",
        json={"owner": "shreyvirmani", "repo": "Devaura"},
    )
    assert prep_res.status_code == 200
    prep_data = prep_res.json()
    assert prep_data["repair_id"] == repair_id
    assert prep_data["status"] == "AWAITING_PR_APPROVAL"
    ctx = prep_data["context"]
    assert ctx["repair_branch"].startswith("devaura/repair/")
    assert ctx["pr_title"].startswith("fix")
    assert "## Summary" in ctx["pr_body"]

    # 2. Get Context
    ctx_res = await client.get(f"/api/v1/repairs/{repair_id}/pr/context")
    assert ctx_res.status_code == 200
    assert ctx_res.json()["repair_branch"] == ctx["repair_branch"]

    # 3. Guard: Prohibit agent self-approval
    agent_appr = await client.post(
        f"/api/v1/repairs/{repair_id}/pr/approve",
        json={"approver": "devaura-agent"},
    )
    assert agent_appr.status_code == 403

    # 4. Human Approval
    human_appr = await client.post(
        f"/api/v1/repairs/{repair_id}/pr/approve",
        json={"approver": "lead-engineer@devaura.ai", "comments": "Verified fix ready for merge."},
    )
    assert human_appr.status_code == 200
    appr_data = human_appr.json()
    token = appr_data["approval_token"]
    assert token.startswith("pr-auth-")
    assert appr_data["status"] == "APPROVED"

    # 5. Create Pull Request with invalid token -> 403
    bad_create = await client.post(
        f"/api/v1/repairs/{repair_id}/pr/create",
        json={"approval_token": "tampered_token", "approver": "lead-engineer@devaura.ai"},
    )
    assert bad_create.status_code in {403, 409}

    # 6. Create Pull Request with valid token -> 201 Created
    good_create = await client.post(
        f"/api/v1/repairs/{repair_id}/pr/create",
        json={"approval_token": token, "approver": "lead-engineer@devaura.ai"},
    )
    assert good_create.status_code == 201
    pr_data = good_create.json()
    assert pr_data["pr_number"] >= 1
    assert "github.com" in pr_data["pr_url"]
    assert pr_data["status"] == "PR_CREATED"

    # 7. Duplicate PR Creation -> 409 Conflict
    dup_create = await client.post(
        f"/api/v1/repairs/{repair_id}/pr/create",
        json={"approval_token": token, "approver": "lead-engineer@devaura.ai"},
    )
    assert dup_create.status_code == 409

    # 8. Query PR details
    get_pr = await client.get(f"/api/v1/repairs/{repair_id}/pr")
    assert get_pr.status_code == 200
    assert get_pr.json()["pr_number"] == pr_data["pr_number"]

    # 9. Query PR Status (CI & Reviews)
    status_res = await client.get(f"/api/v1/repairs/{repair_id}/pr/status")
    assert status_res.status_code == 200
    assert status_res.json()["repair_id"] == repair_id

    # 10. Audit History
    hist_res = await client.get(f"/api/v1/repairs/{repair_id}/pr/history")
    assert hist_res.status_code == 200
    events = hist_res.json()
    assert len(events) >= 2
    event_types = [e["event_type"] for e in events]
    assert "PR_CREATED" in event_types
    assert "PR_PREPARED" in event_types

    # 11. List All PRs
    list_res = await client.get("/api/v1/pull-requests")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


@pytest.mark.asyncio
async def test_pr_rejection_flow(client: AsyncClient, verified_repair):
    repair_id = verified_repair["id"]

    await client.post(f"/api/v1/repairs/{repair_id}/pr/prepare")

    reject_res = await client.post(
        f"/api/v1/repairs/{repair_id}/pr/reject",
        json={"approver": "human-reviewer", "reason": "Requires further refactoring."},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "PR_REJECTED"

    # Verify audit event logged
    hist_res = await client.get(f"/api/v1/repairs/{repair_id}/pr/history")
    events = hist_res.json()
    assert any(e["event_type"] == "PR_REJECTED" for e in events)
