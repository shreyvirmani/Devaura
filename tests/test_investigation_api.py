"""Phase 4 API & State Machine Integration Tests.

Validates all 6 REST endpoints:
- POST /api/v1/investigations
- GET  /api/v1/investigations/{id}
- POST /api/v1/investigations/{id}/run
- GET  /api/v1/investigations/{id}/evidence
- GET  /api/v1/investigations/{id}/candidates
- GET  /api/v1/investigations/{id}/timeline
And verifies strict InvestigationStateMachine transitions.
"""

from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agent.models import (
    EvidenceSufficiency,
    FailureType,
    InvestigationState,
)
from agent.state_machine import InvestigationStateMachine, InvalidStateTransitionError
from apps.api.main import app
from database.connection import close_db, init_db

FIXTURE_DIR = str(Path(__file__).parent / "fixtures" / "validation_repo")


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


@pytest.mark.asyncio
async def test_investigation_api_crud_and_run(client: AsyncClient):
    # 1. Register a test repository
    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "owner": "shreyvirmani",
            "name": "validation_repo",
            "provider": "github",
            "default_branch": "main",
            "clone_url": FIXTURE_DIR,
        },
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]

    # 2. Create Phase 4 Investigation
    create_payload = {
        "repository_id": repo_id,
        "title": "Auth failure during token decoding",
        "failure_type": FailureType.TEST_FAILURE.value,
        "error_message": "AssertionError: token signature expired",
        "stack_trace": """
Traceback (most recent call last):
  File "app/auth.py", line 25, in verify_password
    return hash_password(password) == stored_hash
AssertionError: token signature expired
""",
        "failed_tests": [
            {
                "test_file": "tests/test_auth.py",
                "test_function": "test_verify_password",
                "assertion": "assert verify_password(...) is True",
                "expected": "True",
                "actual": "False",
            }
        ],
    }
    create_res = await client.post("/api/v1/investigations", json=create_payload)
    assert create_res.status_code == 201
    inv_data = create_res.json()
    inv_id = inv_data["id"]
    assert inv_data["title"] == "Auth failure during token decoding"
    assert inv_data["failure_type"] == FailureType.TEST_FAILURE.value
    assert inv_data["status"] == InvestigationState.CREATED.value

    # 3. Get single investigation
    get_res = await client.get(f"/api/v1/investigations/{inv_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == inv_id

    # 4. Run Investigation Engine via API
    run_res = await client.post(f"/api/v1/investigations/{inv_id}/run?workspace={FIXTURE_DIR}")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == InvestigationState.COMPLETED.value
    assert run_data["evidence_sufficiency"] in (
        EvidenceSufficiency.SUFFICIENT.value,
        EvidenceSufficiency.PARTIALLY_SUFFICIENT.value,
    )
    assert len(run_data["evidence_items"]) > 0
    assert len(run_data["root_cause_candidates"]) > 0
    assert len(run_data["investigation_steps"]) >= 4

    # 5. GET /evidence endpoint
    ev_res = await client.get(f"/api/v1/investigations/{inv_id}/evidence")
    assert ev_res.status_code == 200
    evidence_items = ev_res.json()
    assert len(evidence_items) > 0
    # Verify sorting by relevance descending
    relevances = [e["relevance"] for e in evidence_items]
    assert relevances == sorted(relevances, reverse=True)

    # 6. GET /candidates endpoint
    cand_res = await client.get(f"/api/v1/investigations/{inv_id}/candidates")
    assert cand_res.status_code == 200
    candidates = cand_res.json()
    assert len(candidates) > 0
    assert candidates[0]["confidence"] > 0.50
    assert len(candidates[0]["supporting_evidence_ids"]) > 0

    # 7. GET /timeline endpoint
    timeline_res = await client.get(f"/api/v1/investigations/{inv_id}/timeline")
    assert timeline_res.status_code == 200
    steps = timeline_res.json()
    assert len(steps) >= 4
    # Steps in sequential order
    step_numbers = [s["step_number"] for s in steps]
    assert step_numbers == sorted(step_numbers)


def test_investigation_state_machine_transitions():
    """Verify state machine allows legal transitions and rejects illegal transitions."""
    sm = InvestigationStateMachine(InvestigationState.CREATED)
    assert sm.current_state == InvestigationState.CREATED

    # Legal progression
    assert sm.transition(InvestigationState.COLLECTING_EVIDENCE) == InvestigationState.COLLECTING_EVIDENCE
    assert sm.transition(InvestigationState.EVIDENCE_READY) == InvestigationState.EVIDENCE_READY
    assert sm.transition(InvestigationState.ANALYZING) == InvestigationState.ANALYZING
    assert sm.transition(InvestigationState.CANDIDATES_GENERATED) == InvestigationState.CANDIDATES_GENERATED
    assert sm.transition(InvestigationState.COMPLETED) == InvestigationState.COMPLETED

    # Illegal transition from terminal state
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(InvestigationState.COLLECTING_EVIDENCE)

    # Illegal jump from CREATED directly to COMPLETED
    sm2 = InvestigationStateMachine(InvestigationState.CREATED)
    with pytest.raises(InvalidStateTransitionError):
        sm2.transition(InvestigationState.COMPLETED)

    # Legal failure transition from any active state
    sm3 = InvestigationStateMachine(InvestigationState.ANALYZING)
    assert sm3.transition(InvestigationState.FAILED) == InvestigationState.FAILED
