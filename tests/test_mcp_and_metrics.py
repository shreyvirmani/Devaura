import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from apps.api.main import app
from database.connection import close_db, init_db
from database.models import AgentState, CheckStatus, RepairAttempt, VerificationRun


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
async def test_mcp_servers_registration_and_tools(client: AsyncClient):
    # Register an MCP server
    server_payload = {
        "name": "github-mcp",
        "transport": "stdio",
        "endpoint": "npx -y @modelcontextprotocol/server-github",
        "configuration": {"repo_scope": "public"},
    }
    res = await client.post("/api/v1/mcp/servers", json=server_payload)
    assert res.status_code == 201
    server_data = res.json()
    assert server_data["name"] == "github-mcp"
    server_id = server_data["id"]

    # Duplicate registration should return 409
    dup_res = await client.post("/api/v1/mcp/servers", json=server_payload)
    assert dup_res.status_code == 409

    # List MCP servers
    list_res = await client.get("/api/v1/mcp/servers")
    assert list_res.status_code == 200
    servers = list_res.json()
    assert any(s["id"] == server_id for s in servers)

    # Get tools for server
    tools_res = await client.get(f"/api/v1/mcp/servers/{server_id}/tools")
    assert tools_res.status_code == 200
    assert isinstance(tools_res.json(), list)


@pytest.mark.asyncio
async def test_platform_metrics_and_trace(client: AsyncClient):
    metrics_res = await client.get("/api/v1/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert "total_investigations" in metrics
    assert "repair_success_rate_pct" in metrics
    assert "total_mcp_tool_calls" in metrics

    exec_res = await client.get("/api/v1/executions")
    assert exec_res.status_code == 200
    assert isinstance(exec_res.json(), list)


@pytest.mark.asyncio
async def test_approval_and_rejection_gates(client: AsyncClient):
    # Register repo
    repo = (await client.post(
        "/api/v1/repositories",
        json={
            "owner": "shreyvirmani",
            "name": "Devaura",
            "provider": "github",
            "default_branch": "main",
            "clone_url": "https://github.com/shreyvirmani/Devaura.git",
        },
    )).json()

    # Create investigation
    inv = (await client.post(
        "/api/v1/investigations",
        json={
            "repository_id": repo["id"],
            "source_type": "issue",
            "source_id": "99",
            "summary": "JWT signature verification error",
        },
    )).json()

    # Reject investigation
    reject_res = await client.post(f"/api/v1/investigations/{inv['id']}/reject?reason=NotABug")
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == AgentState.IDLE.value
