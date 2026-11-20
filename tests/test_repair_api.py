"""Phase 5 Repair REST API & State Machine Integration Tests.

Validates all repair endpoints and state transitions:
- POST /api/v1/repairs
- GET  /api/v1/repairs
- GET  /api/v1/repairs/{id}
- POST /api/v1/repairs/{id}/context
- POST /api/v1/repairs/{id}/plan
- POST /api/v1/repairs/{id}/patch
- GET  /api/v1/repairs/{id}/risk
- GET  /api/v1/repairs/{id}/diff
- POST /api/v1/repairs/{id}/approve
- POST /api/v1/repairs/{id}/reject
- POST /api/v1/repairs/{id}/apply
"""

import os
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agent.repair.models import ApprovalStatus, RepairState
from agent.repair.state_machine import (
    InvalidRepairStateTransitionError,
    RepairStateMachine,
)
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


def test_repair_state_machine_valid_transitions():
    sm = RepairStateMachine(RepairState.CREATED)
    assert sm.current_state == RepairState.CREATED

    sm.transition(RepairState.CONTEXT_BUILDING)
    assert sm.current_state == RepairState.CONTEXT_BUILDING

    sm.transition(RepairState.CONTEXT_READY)
    assert sm.current_state == RepairState.CONTEXT_READY

    sm.transition(RepairState.PLANNING)
    assert sm.current_state == RepairState.PLANNING

    sm.transition(RepairState.PLAN_READY)
    assert sm.current_state == RepairState.PLAN_READY

    sm.transition(RepairState.PATCH_GENERATING)
    assert sm.current_state == RepairState.PATCH_GENERATING

    sm.transition(RepairState.PATCH_READY)
    assert sm.current_state == RepairState.PATCH_READY

    sm.transition(RepairState.RISK_ANALYZED)
    assert sm.current_state == RepairState.RISK_ANALYZED

    sm.transition(RepairState.AWAITING_APPROVAL)
    assert sm.current_state == RepairState.AWAITING_APPROVAL

    sm.transition(RepairState.APPROVED)
    assert sm.current_state == RepairState.APPROVED

    sm.transition(RepairState.APPLYING)
    assert sm.current_state == RepairState.APPLYING

    sm.transition(RepairState.PATCH_APPLIED_PENDING_VERIFICATION)
    assert sm.current_state == RepairState.PATCH_APPLIED_PENDING_VERIFICATION


def test_repair_state_machine_illegal_transition():
    sm = RepairStateMachine(RepairState.CREATED)
    with pytest.raises(InvalidRepairStateTransitionError):
        sm.transition(RepairState.APPROVED)

    with pytest.raises(InvalidRepairStateTransitionError):
        sm.transition(RepairState.PATCH_APPLIED_PENDING_VERIFICATION)


@pytest.mark.asyncio
async def test_repair_api_full_lifecycle(client: AsyncClient):
    # 1. Setup repository
    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "owner": "test-owner",
            "name": "test-repo",
            "clone_url": "https://github.com/test-owner/test-repo.git",
        },
    )
    assert repo_res.status_code in [200, 201]
    repo_id = repo_res.json()["id"]

    # 2. Setup investigation
    inv_res = await client.post(
        "/api/v1/investigations",
        json={
            "repository_id": repo_id,
            "title": "Auth failure",
            "failure_type": "RUNTIME_ERROR",
            "error_message": "IndexError: list index out of range",
            "stack_trace": 'File "apps/api/auth.py", line 28, in get_current_user\n    token = authorization.split()[1]',
        },
    )
    assert inv_res.status_code == 201
    inv_id = inv_res.json()["id"]

    # Run investigation to generate candidates & evidence
    run_res = await client.post(f"/api/v1/investigations/{inv_id}/run")
    assert run_res.status_code == 200

    # 3. Create repair lifecycle
    rep_res = await client.post(
        "/api/v1/repairs",
        json={"investigation_id": inv_id},
    )
    assert rep_res.status_code == 201
    repair = rep_res.json()
    assert repair["status"] == "CREATED"
    repair_id = repair["id"]

    # List repairs
    list_res = await client.get(f"/api/v1/repairs?investigation_id={inv_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Build context
    ctx_res = await client.post(f"/api/v1/repairs/{repair_id}/context")
    assert ctx_res.status_code == 200
    ctx_data = ctx_res.json()
    assert ctx_data["status"] == "CONTEXT_READY"
    assert ctx_data["context"] is not None
    assert ctx_data["context"]["is_valid"] is True

    # 5. Formulate plan
    plan_res = await client.post(f"/api/v1/repairs/{repair_id}/plan")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["status"] == "PLAN_READY"
    assert plan_data["plan"] is not None
    assert len(plan_data["plan"]["proposed_changes"]) >= 1

    # 6. Generate patch and risk analysis
    patch_res = await client.post(f"/api/v1/repairs/{repair_id}/patch")
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["status"] == "AWAITING_APPROVAL"
    assert patch_data["patch"] is not None
    patch_hash = patch_data["patch"]["patch_hash"]
    assert len(patch_hash) == 64

    # 7. Get risk & diff
    risk_res = await client.get(f"/api/v1/repairs/{repair_id}/risk")
    assert risk_res.status_code == 200
    assert risk_res.json()["level"] in ["LOW", "MEDIUM", "HIGH"]

    diff_res = await client.get(f"/api/v1/repairs/{repair_id}/diff")
    assert diff_res.status_code == 200
    assert diff_res.json()["patch_hash"] == patch_hash

    # 8. Human Approval
    appr_res = await client.post(
        f"/api/v1/repairs/{repair_id}/approve",
        json={"patch_hash": patch_hash},
    )
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["status"] == "APPROVED"
    assert appr_data["approval"]["status"] == "APPROVED"

    # 9. Apply patch to isolated sandbox
    apply_res = await client.post(f"/api/v1/repairs/{repair_id}/apply")
    assert apply_res.status_code == 200
    apply_data = apply_res.json()
    assert apply_data["repair"]["status"] == "PATCH_APPLIED_PENDING_VERIFICATION"
    assert apply_data["execution_result"]["application_status"] == "APPLIED"
    assert apply_data["execution_result"]["verification_status"] == "PENDING"


@pytest.mark.asyncio
async def test_repair_api_rejection_flow(client: AsyncClient):
    # Setup repository & investigation
    repo_res = await client.post(
        "/api/v1/repositories",
        json={"owner": "o", "name": "r", "clone_url": "https://github.com/o/r.git"},
    )
    repo_id = repo_res.json()["id"]

    inv_res = await client.post(
        "/api/v1/investigations",
        json={
            "repository_id": repo_id,
            "title": "Auth failure",
            "failure_type": "RUNTIME_ERROR",
            "error_message": "IndexError: list index out of range",
            "stack_trace": 'File "apps/api/auth.py", line 28, in get_current_user\n    token = authorization.split()[1]',
        },
    )
    inv_id = inv_res.json()["id"]
    await client.post(f"/api/v1/investigations/{inv_id}/run")

    rep_res = await client.post("/api/v1/repairs", json={"investigation_id": inv_id})
    repair_id = rep_res.json()["id"]

    await client.post(f"/api/v1/repairs/{repair_id}/context")
    await client.post(f"/api/v1/repairs/{repair_id}/plan")
    await client.post(f"/api/v1/repairs/{repair_id}/patch")

    # Reject patch
    reject_res = await client.post(
        f"/api/v1/repairs/{repair_id}/reject",
        json={"reason": "Testing rejection flow."},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"
    assert reject_res.json()["approval"]["status"] == "REJECTED"

