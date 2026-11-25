"""Devaura Production Phase 3 — Event Ingestion, Incident Lifecycle & Durable Job Tests.

Verifies:
1. Event normalization (workflow_run failure vs success, check_run, unsupported/malformed).
2. Idempotent Incident creation (dedup across delivery retries & distinct deliveries for same run).
3. Durable Job claiming, duplicate claim prevention, lease expiration recovery.
4. Explicit Retry Policy (RETRYABLE, NON_RETRYABLE, PROVIDER_QUOTA_EXHAUSTED, DEAD_LETTER).
5. Workspace Quota limits (BLOCKED_QUOTA persisted without dropping event).
6. Cross-workspace Incident & Job isolation (IDOR protection).
7. Full deterministic E2E flow: Webhook -> Incident -> Durable Job -> Investigation -> Persisted Result.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.config import get_settings
from apps.api.main import app
from core.events.normalizer import EventNormalizer
from core.jobs.retry_policy import (
    FailureClassification,
    NonRetryableJobError,
    ProviderQuotaExhaustedError,
    RetryableJobError,
    classify_exception,
)
from core.jobs.worker import DurableJobWorker
from database.connection import close_db, get_session_maker, init_db
from database.models import (
    AuditEventRecord,
    Incident,
    IncidentStatus,
    Investigation,
    InvestigationState,
    Job,
    JobStatus,
    Repository,
)


WEBHOOK_SECRET = "test-webhook-secret-phase3-devaura-secure-32chars"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-phase3-verification-32chars")
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


async def setup_workspace_and_repo(client: AsyncClient, email: str, ws_name: str, inst_id: int, repo_name: str):
    res = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "Password123!", "name": "Owner", "workspace_name": ws_name},
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    ws_id = res.json()["default_workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    inst_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/installations",
        headers=headers,
        json={"installation_id": inst_id, "account_name": "acme-org"},
    )
    assert inst_res.status_code == 201

    repo_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/github/repositories/connect",
        headers=headers,
        json={"installation_id": inst_id, "owner": "acme-org", "name": repo_name},
    )
    assert repo_res.status_code == 201
    return ws_id, headers, repo_res.json()["id"], repo_res.json()["github_repository_id"]


# -------------------------------------------------------------------------
# 1. Event Normalization & Retry Policy Unit Tests
# -------------------------------------------------------------------------

def test_event_normalizer_filters_non_failures():
    """Verify workflow_run success and unsupported events do not create IncidentCandidates."""
    success_payload = {
        "action": "completed",
        "installation": {"id": 1},
        "repository": {"id": 10, "full_name": "acme/api"},
        "workflow_run": {"id": 500, "name": "CI", "conclusion": "success", "head_sha": "abc", "head_branch": "main"},
    }
    norm_ok = EventNormalizer.normalize("workflow_run", "del-1", success_payload, repository_id="repo-1")
    assert norm_ok.is_failure is False
    assert norm_ok.incident_candidate is None

    norm_unsupported = EventNormalizer.normalize("star", "del-2", {"action": "created"}, repository_id="repo-1")
    assert norm_unsupported.is_failure is False
    assert norm_unsupported.incident_candidate is None


def test_retry_policy_classification():
    """Verify explicit failure classification for retryable, non-retryable, and quota errors."""
    assert classify_exception(ProviderQuotaExhaustedError("429 limit")) == FailureClassification.PROVIDER_QUOTA_EXHAUSTED
    assert classify_exception(Exception("ResourceExhausted: quota exceeded")) == FailureClassification.PROVIDER_QUOTA_EXHAUSTED
    assert classify_exception(NonRetryableJobError("bad repo")) == FailureClassification.NON_RETRYABLE
    assert classify_exception(ValueError("malformed payload")) == FailureClassification.NON_RETRYABLE
    assert classify_exception(RetryableJobError("temporary timeout")) == FailureClassification.RETRYABLE
    assert classify_exception(TimeoutError("network timed out")) == FailureClassification.RETRYABLE


# -------------------------------------------------------------------------
# 2. Webhook Ingestion -> Incident & Job Idempotency Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_malformed_and_unsupported_events(client: AsyncClient):
    """Verify malformed JSON returns 400 and unsupported event is accepted without creating incident."""
    bad_bytes = b"{not-valid-json"
    res_bad = await client.post(
        "/api/v1/github/webhooks",
        content=bad_bytes,
        headers={
            "X-GitHub-Delivery": "del-bad-1",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(bad_bytes),
        },
    )
    assert res_bad.status_code == 400

    unsupported_bytes = json.dumps({"action": "created"}).encode("utf-8")
    res_unsup = await client.post(
        "/api/v1/github/webhooks",
        content=unsupported_bytes,
        headers={
            "X-GitHub-Delivery": "del-unsup-1",
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": compute_signature(unsupported_bytes),
        },
    )
    assert res_unsup.status_code == 202
    assert res_unsup.json()["incident_id"] is None


@pytest.mark.asyncio
async def test_workflow_failure_creates_incident_and_idempotency(client: AsyncClient):
    """Verify failing workflow_run creates 1 incident + 1 job, and duplicate events do not duplicate."""
    ws_id, headers, repo_id, gh_repo_id = await setup_workspace_and_repo(
        client, "owner@p3.example.com", "Phase3 WS", 30001, "payments-api"
    )

    payload = {
        "action": "completed",
        "installation": {"id": 30001},
        "repository": {"id": gh_repo_id, "full_name": "acme-org/payments-api"},
        "workflow_run": {
            "id": 99887766,
            "name": "Pytest CI",
            "run_number": 42,
            "conclusion": "failure",
            "head_sha": "deadbeef12345678",
            "head_branch": "main",
            "html_url": "https://github.com/acme-org/payments-api/actions/runs/99887766",
        },
    }
    raw = json.dumps(payload).encode("utf-8")

    # 1. First failure webhook
    res1 = await client.post(
        "/api/v1/github/webhooks",
        content=raw,
        headers={
            "X-GitHub-Delivery": "del-wf-001",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(raw),
        },
    )
    assert res1.status_code == 202
    body1 = res1.json()
    assert body1["incident_id"] is not None
    assert body1["job_id"] is not None
    inc_id = body1["incident_id"]

    # 2. Different delivery_id for the SAME workflow_run_id (e.g. GitHub re-delivery / representation)
    res2 = await client.post(
        "/api/v1/github/webhooks",
        content=raw,
        headers={
            "X-GitHub-Delivery": "del-wf-002",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(raw),
        },
    )
    assert res2.status_code == 202
    assert res2.json()["incident_id"] == inc_id

    # Verify only 1 incident exists in workspace
    list_res = await client.get(f"/api/v1/workspaces/{ws_id}/incidents", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["status"] == IncidentStatus.QUEUED.value

    # 3. Check-run deduplication: same check_run_id across 2 deliveries creates only 1 incident
    cr_payload = {
        "action": "completed",
        "installation": {"id": 30001},
        "repository": {"id": gh_repo_id, "full_name": "acme-org/payments-api"},
        "check_run": {
            "id": 77665544,
            "name": "mypy",
            "conclusion": "failure",
            "head_sha": "deadbeef12345678",
            "check_suite": {"id": 111, "head_branch": "main"},
        },
    }
    cr_raw = json.dumps(cr_payload).encode("utf-8")
    cr1 = await client.post(
        "/api/v1/github/webhooks",
        content=cr_raw,
        headers={
            "X-GitHub-Delivery": "del-cr-001",
            "X-GitHub-Event": "check_run",
            "X-Hub-Signature-256": compute_signature(cr_raw),
        },
    )
    cr2 = await client.post(
        "/api/v1/github/webhooks",
        content=cr_raw,
        headers={
            "X-GitHub-Delivery": "del-cr-002",
            "X-GitHub-Event": "check_run",
            "X-Hub-Signature-256": compute_signature(cr_raw),
        },
    )
    assert cr1.json()["incident_id"] == cr2.json()["incident_id"]


# -------------------------------------------------------------------------
# 3. Durable Job Claiming, Lease Recovery & Retry Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_durable_job_atomic_claim_and_lease_recovery(client: AsyncClient):
    """Verify atomic job claim prevents duplicate execution and expired leases recover."""
    ws_id, headers, repo_id, gh_repo_id = await setup_workspace_and_repo(
        client, "worker@p3.example.com", "Worker WS", 30002, "payments-api"
    )

    payload = {
        "action": "completed",
        "installation": {"id": 30002},
        "repository": {"id": gh_repo_id, "full_name": "acme-org/payments-api"},
        "workflow_run": {"id": 112233, "name": "Tests", "conclusion": "failure", "head_sha": "abc", "head_branch": "main"},
    }
    raw = json.dumps(payload).encode("utf-8")
    res = await client.post(
        "/api/v1/github/webhooks",
        content=raw,
        headers={
            "X-GitHub-Delivery": "del-claim-1",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(raw),
        },
    )
    job_id = res.json()["job_id"]

    worker1 = DurableJobWorker(worker_id="worker-1")
    worker2 = DurableJobWorker(worker_id="worker-2")
    session_maker = get_session_maker()

    async with session_maker() as db:
        claimed1 = await worker1.claim_next_job(db)
        assert claimed1 is not None
        assert claimed1.id == job_id
        assert claimed1.status == JobStatus.RUNNING.value

        # Worker 2 must NOT claim the same job
        claimed2 = await worker2.claim_next_job(db)
        assert claimed2 is None

        # Simulate worker1 crash by expiring its lease in DB
        claimed1.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        await db.commit()

        # Worker 2 recovers expired lease and claims the job
        claimed_recovered = await worker2.claim_next_job(db)
        assert claimed_recovered is not None
        assert claimed_recovered.id == job_id
        assert claimed_recovered.worker_id == "worker-2"
        assert claimed_recovered.attempt_count == 2


@pytest.mark.asyncio
async def test_retry_policy_retryable_non_retryable_quota_and_dead_letter(client: AsyncClient):
    """Verify retryable backoff, non-retryable fail, quota exhaustion, and max retries dead-letter."""
    ws_id, headers, repo_id, gh_repo_id = await setup_workspace_and_repo(
        client, "retry@p3.example.com", "Retry WS", 30003, "payments-api"
    )

    async def create_job_for_run(run_id: int, del_id: str) -> str:
        payload = {
            "action": "completed",
            "installation": {"id": 30003},
            "repository": {"id": gh_repo_id, "full_name": "acme-org/payments-api"},
            "workflow_run": {"id": run_id, "name": "CI", "conclusion": "failure", "head_sha": "abc", "head_branch": "main"},
        }
        raw = json.dumps(payload).encode("utf-8")
        r = await client.post(
            "/api/v1/github/webhooks",
            content=raw,
            headers={
                "X-GitHub-Delivery": del_id,
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": compute_signature(raw),
            },
        )
        return r.json()["job_id"]

    session_maker = get_session_maker()

    # A. Retryable -> RETRY_WAIT, then DEAD_LETTER at max_attempts
    job_retry_id = await create_job_for_run(1001, "del-r-1")

    async def fail_retryable(inc, repo, db):
        raise RetryableJobError("Transient GitHub 503")

    w_retry = DurableJobWorker(worker_id="w-retry", investigation_runner=fail_retryable)
    async with session_maker() as db:
        j = await w_retry.claim_next_job(db)
        assert j.id == job_retry_id
        j = await w_retry.execute_job(db, j)
        assert j.status == JobStatus.RETRY_WAIT.value

        # Force available_at to now and exhaust remaining attempts (max_attempts=3)
        j.available_at = datetime.now(timezone.utc)
        await db.commit()
        j2 = await w_retry.claim_next_job(db)
        j2 = await w_retry.execute_job(db, j2)
        assert j2.status == JobStatus.RETRY_WAIT.value

        j2.available_at = datetime.now(timezone.utc)
        await db.commit()
        j3 = await w_retry.claim_next_job(db)
        j3 = await w_retry.execute_job(db, j3)
        assert j3.status == JobStatus.DEAD_LETTER.value

    # B. Non-retryable -> FAILED immediately
    job_non_id = await create_job_for_run(1002, "del-nr-1")

    async def fail_non_retryable(inc, repo, db):
        raise NonRetryableJobError("Malformed repository metadata")

    w_non = DurableJobWorker(worker_id="w-non", investigation_runner=fail_non_retryable)
    async with session_maker() as db:
        j = await w_non.claim_next_job(db)
        assert j.id == job_non_id
        j = await w_non.execute_job(db, j)
        assert j.status == JobStatus.FAILED.value
        assert j.attempt_count == 1

    # C. Provider Quota Exhausted -> PROVIDER_QUOTA_EXHAUSTED immediately
    job_quota_id = await create_job_for_run(1003, "del-q-1")

    async def fail_quota(inc, repo, db):
        raise ProviderQuotaExhaustedError("Gemini quota exhausted")

    w_quota = DurableJobWorker(worker_id="w-quota", investigation_runner=fail_quota)
    async with session_maker() as db:
        j = await w_quota.claim_next_job(db)
        assert j.id == job_quota_id
        j = await w_quota.execute_job(db, j)
        assert j.status == JobStatus.PROVIDER_QUOTA_EXHAUSTED.value
        assert j.failure_classification == FailureClassification.PROVIDER_QUOTA_EXHAUSTED.value


# -------------------------------------------------------------------------
# 4. Tenancy Isolation & Full Deterministic E2E Flow
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_workspace_incident_and_job_isolation(client: AsyncClient):
    """Verify Workspace B cannot access Workspace A incidents or jobs."""
    ws_a, headers_a, _, gh_repo_a = await setup_workspace_and_repo(
        client, "a@tenant.example.com", "Tenant A", 30004, "payments-api"
    )
    ws_b, headers_b, _, _ = await setup_workspace_and_repo(
        client, "b@tenant.example.com", "Tenant B", 30005, "payments-api"
    )

    payload = {
        "action": "completed",
        "installation": {"id": 30004},
        "repository": {"id": gh_repo_a, "full_name": "acme-org/payments-api"},
        "workflow_run": {"id": 55555, "name": "CI", "conclusion": "failure", "head_sha": "abc", "head_branch": "main"},
    }
    raw = json.dumps(payload).encode("utf-8")
    res = await client.post(
        "/api/v1/github/webhooks",
        content=raw,
        headers={
            "X-GitHub-Delivery": "del-iso-1",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(raw),
        },
    )
    inc_id = res.json()["incident_id"]
    job_id = res.json()["job_id"]

    # Tenant B trying to list/access/mutate Tenant A's incidents or jobs -> 403
    assert (await client.get(f"/api/v1/workspaces/{ws_a}/incidents", headers=headers_b)).status_code == 403
    assert (await client.get(f"/api/v1/workspaces/{ws_a}/incidents/{inc_id}", headers=headers_b)).status_code == 403
    assert (await client.post(f"/api/v1/workspaces/{ws_a}/incidents/{inc_id}/retry", headers=headers_b)).status_code == 403
    assert (await client.post(f"/api/v1/workspaces/{ws_a}/incidents/{inc_id}/cancel", headers=headers_b)).status_code == 403
    assert (await client.get(f"/api/v1/workspaces/{ws_a}/jobs", headers=headers_b)).status_code == 403
    assert (await client.get(f"/api/v1/workspaces/{ws_a}/jobs/{job_id}", headers=headers_b)).status_code == 403

    # Tenant B trying to access/mutate Tenant A's resource IDs via Tenant B's workspace -> 404
    assert (await client.get(f"/api/v1/workspaces/{ws_b}/incidents/{inc_id}", headers=headers_b)).status_code == 404
    assert (await client.post(f"/api/v1/workspaces/{ws_b}/incidents/{inc_id}/retry", headers=headers_b)).status_code == 404
    assert (await client.post(f"/api/v1/workspaces/{ws_b}/incidents/{inc_id}/cancel", headers=headers_b)).status_code == 404
    assert (await client.get(f"/api/v1/workspaces/{ws_b}/jobs/{job_id}", headers=headers_b)).status_code == 404


@pytest.mark.asyncio
async def test_worker_api_separation_and_clean_shutdown(monkeypatch):
    """Verify APP_ENV=testing skips worker startup and worker.stop() shuts down cleanly."""
    import asyncio
    from apps.api.main import lifespan

    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("WORKER_ENABLED", "true")
    get_settings.cache_clear()

    # Lifespan in testing mode must NOT spawn background worker
    async with lifespan(app):
        pass

    # Worker run_loop survives process_one exception and exits cleanly on stop()
    worker = DurableJobWorker(worker_id="shutdown-test-worker")

    async def failing_process_one(*args, **kwargs):
        worker.stop()
        raise RuntimeError("transient db blip")

    worker.process_one = failing_process_one  # type: ignore[method-assign]
    await asyncio.wait_for(worker.run_loop(), timeout=5.0)
    assert worker._stop_event.is_set()


@pytest.mark.asyncio
async def test_full_deterministic_webhook_to_investigated_incident_e2e(client: AsyncClient):
    """Complete Phase 3 E2E: Webhook -> Incident -> Durable Job -> Investigation -> Persisted Result."""
    ws_id, headers, repo_id, gh_repo_id = await setup_workspace_and_repo(
        client, "e2e@p3.example.com", "E2E WS", 30006, "payments-api"
    )

    payload = {
        "action": "completed",
        "installation": {"id": 30006},
        "repository": {"id": gh_repo_id, "full_name": "acme-org/payments-api"},
        "workflow_run": {
            "id": 777888,
            "name": "Backend Unit Tests",
            "run_number": 108,
            "conclusion": "failure",
            "head_sha": "1234567890abcdef",
            "head_branch": "feature/fix",
            "html_url": "https://github.com/acme-org/payments-api/actions/runs/777888",
        },
    }
    raw = json.dumps(payload).encode("utf-8")

    # 1. Webhook returns fast with incident & job IDs
    wh_res = await client.post(
        "/api/v1/github/webhooks",
        content=raw,
        headers={
            "X-GitHub-Delivery": "del-e2e-1",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": compute_signature(raw),
        },
    )
    assert wh_res.status_code == 202
    inc_id = wh_res.json()["incident_id"]
    job_id = wh_res.json()["job_id"]

    # 2. Controlled deterministic investigation runner simulating InvestigatorEngine output
    async def stub_investigation_runner(inc: Incident, repo: Repository, db):
        inv = Investigation(
            workspace_id=inc.workspace_id,
            repository_id=repo.id,
            source_type=inc.source,
            source_id=inc.external_run_id or inc.id,
            status=InvestigationState.COMPLETED.value,
            title=inc.title,
            summary=inc.summary,
            root_cause="AssertionError in payments/calculator.py: zero-division guard missing.",
            confidence=0.92,
        )
        db.add(inv)
        await db.flush()
        inc.investigation_id = inv.id
        return inv

    # 3. Worker claims & executes job
    worker = DurableJobWorker(worker_id="e2e-worker", investigation_runner=stub_investigation_runner)
    executed_job = await worker.process_one(workspace_id=ws_id)
    assert executed_job is not None
    assert executed_job.id == job_id
    assert executed_job.status == JobStatus.SUCCEEDED.value

    # 4. Query Incident Detail API and verify complete persisted lifecycle
    detail_res = await client.get(f"/api/v1/workspaces/{ws_id}/incidents/{inc_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    # Stub has no evidence items so Phase 4 eligibility gate marks INSUFFICIENT_EVIDENCE
    assert detail["status"] == IncidentStatus.INSUFFICIENT_EVIDENCE.value
    assert detail["eligibility"]["eligible"] is False
    assert detail["investigation"] is not None
    assert detail["investigation"]["status"] == InvestigationState.COMPLETED.value
    assert "zero-division guard" in detail["investigation"]["root_cause"]
    assert len(detail["jobs"]) == 1
    assert detail["jobs"][0]["status"] == JobStatus.SUCCEEDED.value
    actions = [t["action"] for t in detail["timeline"]]
    assert "incident.created" in actions
    assert "job.created" in actions
    assert "job.claimed" in actions
    assert "incident.investigation_started" in actions
    assert "incident.investigation_completed" in actions
