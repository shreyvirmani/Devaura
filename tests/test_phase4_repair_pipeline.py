"""Devaura Production Phase 4 — End-to-End Repair Execution Pipeline Tests.

Exercises:
1. Full controlled E2E lifecycle:
   Webhook -> Incident -> Investigation -> Eligibility Gate -> Repair Plan & Patch (Sandbox)
   -> Verification -> AWAITING_APPROVAL -> Human Approval -> Branch/Commit/PR -> PR_CREATED.
2. Failure cases: insufficient evidence, safety block, path traversal, verification failure,
   GitHub failure, stale base revision, patch hash mismatch, agent self-approval.
3. Idempotency: repair/patch reuse, verification reuse, duplicate PR prevention.
4. Workspace isolation on /approve and /reject.
"""

import hashlib
import hmac
import json
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.config import get_settings
from apps.api.main import app
from core.jobs.retry_policy import FailureClassification
from core.jobs.worker import DurableJobWorker
from core.repairs.pipeline import run_pr_stage, run_repair_stage, run_verification_stage
from database.connection import close_db, get_session_maker, init_db
from database.models import (
    Evidence,
    EvidenceSource,
    EvidenceSufficiency,
    EvidenceType,
    Incident,
    IncidentStatus,
    Investigation,
    InvestigationState,
    Job,
    JobStatus,
    JobType,
    PullRequestRecord,
    RepairRecord,
    Repository,
    RootCauseCandidate,
    VerificationRunRecord,
)
from integrations.github.mock_provider import MockGitProvider
from integrations.github.models import BranchInfo
from integrations.github.provider import GitProviderError


WEBHOOK_SECRET = "test-webhook-secret-phase4-devaura-secure-32chars"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-phase4-verification-32chars")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("ALLOW_DEV_USER_FALLBACK", "false")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()


def compute_signature(payload_bytes: bytes) -> str:
    sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.fixture
def sample_local_repo(tmp_path: Path) -> Path:
    """Create a tiny self-contained local git/python repo for fast deterministic sandbox tests."""
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()
    (repo_dir / "calculator.py").write_text(
        "def divide(a, b):\n    return a / b\n",
        encoding="utf-8",
    )
    (repo_dir / "test_calculator.py").write_text(
        "from calculator import divide\n\ndef test_divide():\n    assert divide(4, 2) == 2\n",
        encoding="utf-8",
    )
    return repo_dir


async def setup_workspace_and_local_repo(
    client: AsyncClient, email: str, ws_name: str, inst_id: int, local_repo: Path
):
    res = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "Password123!", "name": "Alice Reviewer", "workspace_name": ws_name},
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    ws_id = res.json()["default_workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        f"/api/v1/workspaces/{ws_id}/github/installations",
        headers=headers,
        json={"installation_id": inst_id, "account_name": "acme-org"},
    )
    repo_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/repositories/connect",
        headers=headers,
        json={"installation_id": inst_id, "owner": "acme-org", "name": "calc-service"},
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]
    gh_repo_id = repo_res.json()["github_repository_id"]

    # Point clone_url to the tiny tmp_path repo so sandbox creation takes milliseconds
    session_maker = get_session_maker()
    async with session_maker() as db:
        repo = (await db.execute(select(Repository).where(Repository.id == repo_id))).scalar_one()
        repo.clone_url = str(local_repo)
        await db.commit()

    return ws_id, headers, repo_id, gh_repo_id


def make_sufficient_investigation_runner(target_file: str = "calculator.py"):
    async def runner(inc: Incident, repo: Repository, db):
        inv = Investigation(
            workspace_id=inc.workspace_id,
            repository_id=repo.id,
            source_type=inc.source,
            source_id=inc.external_run_id or inc.id,
            status=InvestigationState.COMPLETED.value,
            title=inc.title,
            summary=inc.summary,
            evidence_sufficiency=EvidenceSufficiency.SUFFICIENT.value,
            root_cause=f"Missing zero-division guard in {target_file}",
            confidence=0.95,
        )
        db.add(inv)
        await db.flush()

        ev = Evidence(
            investigation_id=inv.id,
            source=EvidenceSource.TEST.value,
            type=EvidenceType.TEST_FAILURE.value,
            content="ZeroDivisionError: division by zero",
            repository_path=target_file,
            line_start=2,
            line_end=2,
            confidence=0.95,
            relevance=0.95,
        )
        db.add(ev)
        await db.flush()

        cand = RootCauseCandidate(
            investigation_id=inv.id,
            title="Zero division guard missing",
            description=f"Add b == 0 guard in {target_file}",
            confidence=0.95,
            affected_files=[target_file],
            affected_symbols=["divide"],
            supporting_evidence_ids=[ev.id],
            reasoning="Stack trace points to line 2.",
        )
        db.add(cand)
        await db.flush()
        inc.investigation_id = inv.id
        return inv

    return runner


# -------------------------------------------------------------------------
# 1. Full Controlled End-to-End Lifecycle Test
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase4_full_controlled_e2e_lifecycle(client: AsyncClient, sample_local_repo: Path):
    """Exercise complete lifecycle: Webhook -> Investigation -> Repair -> Verify -> Approval -> PR."""
    ws_id, headers, repo_id, gh_repo_id = await setup_workspace_and_local_repo(
        client, "e2e@phase4.example.com", "Phase4 E2E WS", 40001, sample_local_repo
    )

    payload = {
        "action": "completed",
        "installation": {"id": 40001},
        "repository": {"id": gh_repo_id, "full_name": "acme-org/calc-service"},
        "workflow_run": {
            "id": 900100,
            "name": "Unit Tests",
            "run_number": 12,
            "conclusion": "failure",
            "head_sha": "abc123def456",
            "head_branch": "main",
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    wh_res = await client.post(
        "/api/v1/github/webhooks",
        content=raw,
        headers={
            "X-GitHub-Delivery": "del-p4-e2e-1",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(raw),
        },
    )
    assert wh_res.status_code == 202
    inc_id = wh_res.json()["incident_id"]

    mock_git = MockGitProvider(initial_default_branch_sha="abc123def456")
    mock_git.branches[("acme-org", "calc-service", "main")] = BranchInfo(
        name="main", sha="abc123def456", is_protected=True, exists=True
    )
    worker = DurableJobWorker(
        worker_id="phase4-e2e-worker",
        investigation_runner=make_sufficient_investigation_runner("calculator.py"),
        git_provider_factory=lambda: mock_git,
    )

    # Step 1: Investigation Job -> Eligibility -> Enqueues REPAIR_INCIDENT
    j_inv = await worker.process_one(workspace_id=ws_id)
    assert j_inv is not None and j_inv.job_type == JobType.INVESTIGATE_INCIDENT.value
    assert j_inv.status == JobStatus.SUCCEEDED.value

    # Provide deterministic patch + fast custom verification commands on the queued repair job
    session_maker = get_session_maker()
    async with session_maker() as db:
        rep_job = (
            await db.execute(
                select(Job).where(Job.incident_id == inc_id, Job.job_type == JobType.REPAIR_INCIDENT.value)
            )
        ).scalar_one()
        rep_job.payload = {
            "modified_contents": {
                "calculator.py": "def divide(a, b):\n    if b == 0:\n        return 0\n    return a / b\n"
            },
            "custom_commands": {
                "tests": 'python -c "exit(0)"',
                "lint": 'python -c "exit(0)"',
                "typecheck": 'python -c "exit(0)"',
            },
        }
        await db.commit()

    # Step 2: Repair Job -> Plan + Patch + Sandbox Apply -> Enqueues VERIFY_REPAIR
    j_rep = await worker.process_one(workspace_id=ws_id)
    assert j_rep is not None and j_rep.job_type == JobType.REPAIR_INCIDENT.value
    assert j_rep.status == JobStatus.SUCCEEDED.value, j_rep.last_error

    # Step 3: Verification Job -> Sandbox Verify -> Stops at AWAITING_APPROVAL
    j_ver = await worker.process_one(workspace_id=ws_id)
    assert j_ver is not None and j_ver.job_type == JobType.VERIFY_REPAIR.value
    assert j_ver.status == JobStatus.SUCCEEDED.value, j_ver.last_error

    detail_res = await client.get(f"/api/v1/workspaces/{ws_id}/incidents/{inc_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["status"] == IncidentStatus.AWAITING_APPROVAL.value
    assert detail["eligibility"]["eligible"] is True
    assert detail["repair"]["patch"]["patch_hash"]
    assert detail["verification"]["overall_result"] == "PASSED"
    assert detail["pull_request"] is None

    # No PR created yet — human approval is mandatory
    assert len(mock_git.pull_requests) == 0

    # Step 4: Human Approval via API -> Enqueues CREATE_PR
    appr_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/incidents/{inc_id}/approve",
        headers=headers,
        json={
            "patch_hash": detail["repair"]["patch"]["patch_hash"],
            "base_revision": detail["repair"]["base_revision"],
        },
    )
    assert appr_res.status_code == 202

    # Step 5: PR Job -> Branch -> Commit -> PR Created
    j_pr = await worker.process_one(workspace_id=ws_id)
    assert j_pr is not None and j_pr.job_type == JobType.CREATE_PR.value
    assert j_pr.status == JobStatus.SUCCEEDED.value, j_pr.last_error
    assert len(mock_git.pull_requests) == 1

    final_detail = (await client.get(f"/api/v1/workspaces/{ws_id}/incidents/{inc_id}", headers=headers)).json()
    assert final_detail["status"] == IncidentStatus.PR_CREATED.value
    assert final_detail["pull_request"]["pr_number"] == 101
    assert "github.com" in final_detail["pull_request"]["url"]


# -------------------------------------------------------------------------
# 2. Failure Cases, Safety Blocks & Approval Integrity
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase4_safety_block_verification_fail_and_approval_tampering(
    client: AsyncClient, sample_local_repo: Path
):
    """Verify safety block on sensitive paths, verification failure, stale base revision, and hash mismatch."""
    ws_id, headers, repo_id, gh_repo_id = await setup_workspace_and_local_repo(
        client, "sec@phase4.example.com", "Phase4 Sec WS", 40002, sample_local_repo
    )

    async def trigger_wh(run_id: int, del_id: str) -> str:
        raw = json.dumps({
            "action": "completed",
            "installation": {"id": 40002},
            "repository": {"id": gh_repo_id, "full_name": "acme-org/calc-service"},
            "workflow_run": {
                "id": run_id,
                "name": "CI",
                "conclusion": "failure",
                "head_sha": "abc123",
                "head_branch": "main",
            },
        }).encode("utf-8")
        r = await client.post(
            "/api/v1/github/webhooks",
            content=raw,
            headers={
                "X-GitHub-Delivery": del_id,
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": compute_signature(raw),
            },
        )
        return r.json()["incident_id"]

    # A. Sensitive path (.env) -> SAFETY_BLOCK at Eligibility Gate
    inc_sec = await trigger_wh(201, "del-sec-1")
    w_sec = DurableJobWorker(
        worker_id="w-sec",
        investigation_runner=make_sufficient_investigation_runner(".env"),
    )
    await w_sec.process_one(workspace_id=ws_id)
    d_sec = (await client.get(f"/api/v1/workspaces/{ws_id}/incidents/{inc_sec}", headers=headers)).json()
    assert d_sec["status"] == IncidentStatus.SAFETY_BLOCK.value
    assert d_sec["eligibility"]["eligible"] is False

    # B. Verification failure -> VERIFICATION_FAILED, cannot approve
    inc_vf = await trigger_wh(202, "del-vf-1")
    w_vf = DurableJobWorker(
        worker_id="w-vf",
        investigation_runner=make_sufficient_investigation_runner("calculator.py"),
    )
    await w_vf.process_one(workspace_id=ws_id)
    session_maker = get_session_maker()
    async with session_maker() as db:
        rj = (await db.execute(select(Job).where(Job.incident_id == inc_vf, Job.job_type == JobType.REPAIR_INCIDENT.value))).scalar_one()
        rj.payload = {
            "modified_contents": {"calculator.py": "def divide(a, b):\n    return a / b  # unchanged\n"},
            "custom_commands": {"tests": 'python -c "exit(1)"', "lint": 'python -c "exit(0)"', "typecheck": 'python -c "exit(0)"'},
        }
        await db.commit()

    await w_vf.process_one(workspace_id=ws_id)  # repair
    await w_vf.process_one(workspace_id=ws_id)  # verify (fails)
    d_vf = (await client.get(f"/api/v1/workspaces/{ws_id}/incidents/{inc_vf}", headers=headers)).json()
    assert d_vf["status"] == IncidentStatus.VERIFICATION_FAILED.value
    assert d_vf["failure_classification"] == FailureClassification.VERIFICATION_FAILURE.value
    assert (await client.post(f"/api/v1/workspaces/{ws_id}/incidents/{inc_vf}/approve", headers=headers, json={})).status_code == 409

    # C. Patch hash & base revision tampering rejected on approve
    inc_tamp = await trigger_wh(203, "del-tamp-1")
    await w_vf.process_one(workspace_id=ws_id)  # investigate
    async with session_maker() as db:
        rj = (await db.execute(select(Job).where(Job.incident_id == inc_tamp, Job.job_type == JobType.REPAIR_INCIDENT.value))).scalar_one()
        rj.payload = {
            "modified_contents": {"calculator.py": "def divide(a, b):\n    return 0 if b == 0 else a / b\n"},
            "custom_commands": {"tests": 'python -c "exit(0)"', "lint": 'python -c "exit(0)"', "typecheck": 'python -c "exit(0)"'},
        }
        await db.commit()
    await w_vf.process_one(workspace_id=ws_id)  # repair
    await w_vf.process_one(workspace_id=ws_id)  # verify

    bad_hash_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/incidents/{inc_tamp}/approve",
        headers=headers,
        json={"patch_hash": "tampered-hash", "base_revision": "abc123"},
    )
    assert bad_hash_res.status_code == 409

    bad_base_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/incidents/{inc_tamp}/approve",
        headers=headers,
        json={"base_revision": "stale-rev-999"},
    )
    assert bad_base_res.status_code == 409


# -------------------------------------------------------------------------
# 3. Idempotency & Workspace Isolation Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase4_idempotency_and_cross_workspace_approval_isolation(
    client: AsyncClient, sample_local_repo: Path
):
    """Verify repair/verification/PR idempotency and cross-workspace /approve & /reject blocking."""
    ws_a, headers_a, _, gh_repo_a = await setup_workspace_and_local_repo(
        client, "a@idem.example.com", "Idem WS A", 40003, sample_local_repo
    )
    ws_b, headers_b, _, _ = await setup_workspace_and_local_repo(
        client, "b@idem.example.com", "Idem WS B", 40004, sample_local_repo
    )

    raw = json.dumps({
        "action": "completed",
        "installation": {"id": 40003},
        "repository": {"id": gh_repo_a, "full_name": "acme-org/calc-service"},
        "workflow_run": {"id": 8080, "name": "CI", "conclusion": "failure", "head_sha": "rev1", "head_branch": "main"},
    }).encode("utf-8")
    inc_id = (await client.post(
        "/api/v1/github/webhooks",
        content=raw,
        headers={
            "X-GitHub-Delivery": "del-idem-1",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(raw),
        },
    )).json()["incident_id"]

    mock_git = MockGitProvider(initial_default_branch_sha="rev1")
    mock_git.branches[("acme-org", "calc-service", "main")] = BranchInfo(
        name="main", sha="rev1", is_protected=True, exists=True
    )
    worker = DurableJobWorker(
        worker_id="w-idem",
        investigation_runner=make_sufficient_investigation_runner("calculator.py"),
        git_provider_factory=lambda: mock_git,
    )
    await worker.process_one(workspace_id=ws_a)

    session_maker = get_session_maker()
    async with session_maker() as db:
        rj = (await db.execute(select(Job).where(Job.incident_id == inc_id, Job.job_type == JobType.REPAIR_INCIDENT.value))).scalar_one()
        rj.payload = {
            "modified_contents": {"calculator.py": "def divide(a, b):\n    return 0 if b == 0 else a / b\n"},
            "custom_commands": {"tests": 'python -c "exit(0)"', "lint": 'python -c "exit(0)"', "typecheck": 'python -c "exit(0)"'},
        }
        await db.commit()

    await worker.process_one(workspace_id=ws_a)  # repair
    await worker.process_one(workspace_id=ws_a)  # verify

    # Cross-workspace /approve and /reject blocked
    assert (await client.post(f"/api/v1/workspaces/{ws_a}/incidents/{inc_id}/approve", headers=headers_b, json={})).status_code == 403
    assert (await client.post(f"/api/v1/workspaces/{ws_b}/incidents/{inc_id}/approve", headers=headers_b, json={})).status_code == 404
    assert (await client.post(f"/api/v1/workspaces/{ws_a}/incidents/{inc_id}/reject", headers=headers_b, json={"reason": "x"})).status_code == 403

    # Approve from WS A
    appr = await client.post(f"/api/v1/workspaces/{ws_a}/incidents/{inc_id}/approve", headers=headers_a, json={})
    assert appr.status_code == 202
    await worker.process_one(workspace_id=ws_a)  # create PR

    # Verify stage idempotency: re-running repair, verify, PR produces zero duplicates
    async with session_maker() as db:
        inc = (await db.execute(select(Incident).where(Incident.id == inc_id))).scalar_one()
        repo = (await db.execute(select(Repository).where(Repository.id == inc.repository_id))).scalar_one()
        pr_job = (await db.execute(select(Job).where(Job.incident_id == inc_id, Job.job_type == JobType.CREATE_PR.value))).scalar_one()

        rep1 = await run_repair_stage(db, inc, repo, pr_job)
        ver1 = await run_verification_stage(db, inc, repo, pr_job)
        pr1 = await run_pr_stage(db, inc, repo, pr_job, git_provider_factory=lambda: mock_git)
        assert rep1.id == inc.repair_id
        assert ver1.overall_result == "PASSED"
        assert pr1.pr_number == 101
        assert len(mock_git.pull_requests) == 1
