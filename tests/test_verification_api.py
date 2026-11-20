"""Devaura Phase 6 Verification & Bounded Loop REST API Tests.

Tests endpoints:
- POST /api/v1/repairs/{id}/verify
- GET  /api/v1/repairs/{id}/verification
- GET  /api/v1/repairs/{id}/verification/history
- GET  /api/v1/repairs/{id}/attempts
- POST /api/v1/repairs/{id}/retry
- GET  /api/v1/repairs/{id}/status
"""

import os
import shutil
import tempfile
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agent.repair.models import ApprovalStatus, RepairState
from apps.api.main import app
from database.connection import close_db, init_db


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "testing")


@pytest_asyncio.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()


@pytest_asyncio.fixture
async def prepared_repair(client: AsyncClient):
    """Fixture that initializes repo, investigation, repair, plan, patch, approval, and workspace."""
    # 1. Repo
    repo_res = await client.post(
        "/api/v1/repositories",
        json={"owner": "test-org", "name": "verification-repo", "clone_url": "https://github.com/test-org/verification-repo.git", "default_branch": "main"},
    )
    repo = repo_res.json()

    # 2. Investigation with realistic failure description and run
    inv_res = await client.post(
        "/api/v1/investigations",
        json={
            "repository_id": repo["id"],
            "failure_description": "IndexError in get_current_user",
            "issue_title": "IndexError Bug",
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
    rep_res = await client.post(
        "/api/v1/repairs",
        json={"investigation_id": inv_id},
    )
    repair = rep_res.json()
    repair_id = repair["id"]

    # 4. Context
    ctx_res = await client.post(f"/api/v1/repairs/{repair_id}/context")
    assert ctx_res.status_code == 200

    # 5. Plan
    plan_res = await client.post(f"/api/v1/repairs/{repair_id}/plan")
    assert plan_res.status_code == 200

    # 6. Patch
    patch_res = await client.post(f"/api/v1/repairs/{repair_id}/patch")
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    patch_hash = patch_data["patch"]["patch_hash"]

    # 7. Approve
    appr_res = await client.post(f"/api/v1/repairs/{repair_id}/approve", json={"patch_hash": patch_hash})
    assert appr_res.status_code == 200

    # 8. Apply inside sandbox
    apply_res = await client.post(f"/api/v1/repairs/{repair_id}/apply")
    assert apply_res.status_code == 200
    applied_repair = apply_res.json()["repair"]
    assert applied_repair["status"] == "PATCH_APPLIED_PENDING_VERIFICATION"

    return applied_repair


@pytest.mark.asyncio
async def test_verification_passing_flow(client: AsyncClient, prepared_repair):
    repair_id = prepared_repair["id"]

    # Run verification with passing commands
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
    data = verify_res.json()

    # 1. State machine transition to VERIFIED
    assert data["repair"]["status"] == "VERIFIED"
    assert data["verification_run"]["overall_result"] == "PASSED"
    assert len(data["verification_run"]["checks"]) == 3
    assert all(c["status"] == "PASSED" for c in data["verification_run"]["checks"])

    # 2. GET /verification
    get_v_res = await client.get(f"/api/v1/repairs/{repair_id}/verification")
    assert get_v_res.status_code == 200
    assert get_v_res.json()["id"] == data["verification_run"]["id"]

    # 3. GET /status
    status_res = await client.get(f"/api/v1/repairs/{repair_id}/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["is_verified"] is True
    assert status_data["phase7_ready"] is True
    assert status_data["current_attempt"] == 1


@pytest.mark.asyncio
async def test_verification_failure_and_retry_flow(client: AsyncClient, prepared_repair):
    repair_id = prepared_repair["id"]

    # 1. Run verification that fails tests
    verify_res = await client.post(
        f"/api/v1/repairs/{repair_id}/verify",
        json={
            "custom_commands": {
                "tests": 'python -c "exit(1)"',
                "lint": 'python -c "exit(0)"',
                "typecheck": 'python -c "exit(0)"',
            }
        },
    )
    assert verify_res.status_code == 200
    data = verify_res.json()

    assert data["repair"]["status"] == "REPAIR_RETRY_ELIGIBLE"
    assert data["verification_run"]["overall_result"] == "FAILED"
    assert data["verification_run"]["failure_analysis"]["can_retry"] is True

    # 2. Check repair attempts history
    att_res = await client.get(f"/api/v1/repairs/{repair_id}/attempts")
    assert att_res.status_code == 200
    attempts = att_res.json()
    assert len(attempts) >= 1
    assert attempts[0]["attempt_number"] == 1

    # 3. Initiate Retry (Attempt 2)
    retry_res = await client.post(
        f"/api/v1/repairs/{repair_id}/retry",
        json={
            "reason": "Retrying with refined defensive patch",
            "custom_modified_contents": {"apps/api/auth.py": "# modified retry in test 2\n"},
        },
    )
    assert retry_res.status_code == 200
    retried = retry_res.json()

    # Retry should advance attempt and reset approval gate
    assert retried["current_attempt"] == 2
    assert retried["status"] == "AWAITING_APPROVAL"
    assert retried["approval"]["status"] == "PENDING"
    assert retried["approval"]["approved_by"] is None

    # Status summary
    status_res = await client.get(f"/api/v1/repairs/{repair_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["current_attempt"] == 2


@pytest.mark.asyncio
async def test_bounded_attempt_exhaustion(client: AsyncClient, prepared_repair):
    repair_id = prepared_repair["id"]

    fast_fail_cmds = {
        "tests": 'python -c "exit(1)"',
        "lint": 'python -c "exit(0)"',
        "typecheck": 'python -c "exit(0)"',
    }

    # Attempt 1 fail
    await client.post(
        f"/api/v1/repairs/{repair_id}/verify",
        json={"custom_commands": fast_fail_cmds},
    )

    # Retry -> Attempt 2 with modified contents
    retry2 = await client.post(
        f"/api/v1/repairs/{repair_id}/retry",
        json={"custom_modified_contents": {"apps/api/auth.py": "# retry attempt 2\n"}},
    )
    assert retry2.status_code == 200
    p2_hash = retry2.json()["patch"]["patch_hash"]

    # Approve & Apply Attempt 2
    await client.post(f"/api/v1/repairs/{repair_id}/approve", json={"patch_hash": p2_hash})
    await client.post(f"/api/v1/repairs/{repair_id}/apply")

    # Attempt 2 fail
    await client.post(
        f"/api/v1/repairs/{repair_id}/verify",
        json={"custom_commands": fast_fail_cmds},
    )

    # Retry -> Attempt 3 with modified contents
    retry3 = await client.post(
        f"/api/v1/repairs/{repair_id}/retry",
        json={"custom_modified_contents": {"apps/api/auth.py": "# retry attempt 3\n"}},
    )
    assert retry3.status_code == 200
    p3_hash = retry3.json()["patch"]["patch_hash"]

    # Approve & Apply Attempt 3
    await client.post(f"/api/v1/repairs/{repair_id}/approve", json={"patch_hash": p3_hash})
    await client.post(f"/api/v1/repairs/{repair_id}/apply")

    # Attempt 3 fail -> Must transition to REPAIR_EXHAUSTED
    v3_res = await client.post(
        f"/api/v1/repairs/{repair_id}/verify",
        json={"custom_commands": fast_fail_cmds},
    )
    assert v3_res.status_code == 200
    assert v3_res.json()["repair"]["status"] == "REPAIR_EXHAUSTED"

    # Attempt 4 MUST FAIL with 400 Bad Request
    att4_res = await client.post(f"/api/v1/repairs/{repair_id}/retry")
    assert att4_res.status_code == 400
    assert "exhausted" in att4_res.json()["detail"].lower()
