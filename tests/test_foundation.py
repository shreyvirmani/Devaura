import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from apps.api.config import get_settings
from apps.api.logger import redact_secrets, setup_logger
from apps.api.main import app
from database.connection import Base, close_db, get_engine, init_db
from database.models import (
    AgentState,
    CheckStatus,
    Investigation,
    MCPServer,
    MCPTool,
    Repository,
    RiskLevel,
    User,
)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "testing")


@pytest_asyncio.fixture
async def client():
    # Initialize in-memory test database
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Devaura"
    assert "verified fix" in data["tagline"]
    assert data["status"] == "operational"


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Devaura"
    assert "healthy" in data["database"]

    live_res = await client.get("/api/v1/health/live")
    assert live_res.status_code == 200
    assert live_res.json() == {"live": "true"}

    ready_res = await client.get("/api/v1/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json() == {"ready": "true"}


@pytest.mark.asyncio
async def test_repository_crud(client: AsyncClient):
    # 1. Register a repository
    create_payload = {
        "owner": "shreyvirmani",
        "name": "Devaura",
        "provider": "github",
        "default_branch": "main",
        "clone_url": "https://github.com/shreyvirmani/Devaura.git",
    }
    create_res = await client.post("/api/v1/repositories", json=create_payload)
    assert create_res.status_code == 201
    repo_data = create_res.json()
    repo_id = repo_data["id"]
    assert repo_data["name"] == "Devaura"
    assert repo_data["owner"] == "shreyvirmani"

    # 2. List repositories
    list_res = await client.get("/api/v1/repositories")
    assert list_res.status_code == 200
    repos = list_res.json()
    assert len(repos) >= 1
    assert any(r["id"] == repo_id for r in repos)

    # 3. Get single repository
    get_res = await client.get(f"/api/v1/repositories/{repo_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == repo_id


@pytest.mark.asyncio
async def test_investigation_lifecycle_skeleton(client: AsyncClient):
    # Register repository first
    repo_res = await client.post(
        "/api/v1/repositories",
        json={
            "owner": "test-org",
            "name": "payment-service",
            "provider": "github",
            "default_branch": "main",
            "clone_url": "https://github.com/test-org/payment-service.git",
        },
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]

    # Create investigation
    inv_res = await client.post(
        "/api/v1/investigations",
        json={
            "repository_id": repo_id,
            "source_type": "issue",
            "source_id": "42",
            "summary": "Fix malformed authentication token error",
        },
    )
    assert inv_res.status_code == 201
    inv_data = inv_res.json()
    assert inv_data["status"] == AgentState.INVESTIGATING.value
    assert inv_data["source_id"] == "42"


def test_secret_redaction():
    secret_text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy ghp_123456789012345678901234567890123456"
    redacted = redact_secrets(secret_text)
    assert "ghp_" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_agent_state_enums():
    assert AgentState.IDLE.value == "IDLE"
    assert AgentState.INVESTIGATING.value == "INVESTIGATING"
    assert AgentState.PLAN_READY.value == "PLAN_READY"
    assert AgentState.WAITING_FOR_APPROVAL.value == "WAITING_FOR_APPROVAL"
    assert AgentState.REPAIRING.value == "REPAIRING"
    assert AgentState.VERIFYING.value == "VERIFYING"
    assert AgentState.REVIEWING.value == "REVIEWING"
    assert AgentState.PR_CREATED.value == "PR_CREATED"


def test_risk_level_enums():
    assert RiskLevel.SAFE.value == "SAFE"
    assert RiskLevel.CONTROLLED.value == "CONTROLLED"
    assert RiskLevel.DANGEROUS.value == "DANGEROUS"
