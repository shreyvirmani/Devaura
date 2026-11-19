import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from apps.api.main import app
from database.connection import close_db, get_engine, init_db, get_session_maker
from database.models import ToolExecution
from mcp.client.mcp_client import DevauraMCPClient
from mcp.mock_server import create_mock_mcp_server
from mcp.models import (
    MCPApprovalRequiredError,
    MCPServerInfo,
    RiskLevel,
    ServerTrustLevel,
    TransportType,
)
from mcp.registry.registry import registry


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
async def test_mcp_complete_end_to_end_workflow(client: AsyncClient):
    session_factory = get_session_maker()

    # Step 1: Register Mock Server in registry
    mock_instance = create_mock_mcp_server("mock-e2e-server")
    server_id = "srv_mock_e2e"
    info = MCPServerInfo(
        id=server_id,
        name="Mock E2E Server",
        transport=TransportType.NATIVE,
        endpoint="internal://mock-e2e",
        status="disconnected",
        trust_level=ServerTrustLevel.TRUSTED,
    )
    registry._servers[server_id] = info
    registry._clients[server_id] = DevauraMCPClient(info, native_server_instance=mock_instance)

    # Step 2: Connect and Discover Tools
    async with session_factory() as session:
        connected_server = await registry.connect_server(server_id, session=session)
        assert connected_server.status == "connected"
        assert len(connected_server.tools) >= 5

    # Step 3: Agent executes SAFE tool (mock_get_issue) -> Policy ALLOW -> Executes -> Audits
    async with session_factory() as session:
        tool_result = await registry.execute_tool(
            server_id=server_id,
            tool_name="mock_get_issue",
            arguments={"issue_id": 42},
            user_id="usr_developer_01",
            investigation_id="inv_test_e2e_01",
            session=session,
        )
        await session.commit()
        assert not tool_result.is_error
        assert "Mock Issue #42" in tool_result.content

    # Verify audit row created in database
    async with session_factory() as session:
        audit_records = (await session.execute(
            select(ToolExecution).where(ToolExecution.tool == "mock_get_issue")
        )).scalars().all()
        assert len(audit_records) >= 1
        assert audit_records[0].status == "success"
        assert audit_records[0].server == server_id

    # Step 4: Agent requests DANGEROUS tool (mock_dangerous_push) without approval
    # Must raise MCPApprovalRequiredError with approval token
    approval_token = None
    with pytest.raises(MCPApprovalRequiredError) as exc_info:
        async with session_factory() as session:
            await registry.execute_tool(
                server_id=server_id,
                tool_name="mock_dangerous_push",
                arguments={"branch": "devaura/fix-42"},
                user_id="usr_developer_01",
                session=session,
            )
    approval_token = exc_info.value.approval_token
    assert approval_token.startswith("appr_")

    # Step 5: Human operator grants approval via API endpoint
    appr_res = await client.post(
        "/api/v1/mcp/policy/approve",
        json={
            "token": approval_token,
            "tool_name": "mock_dangerous_push",
            "approved": True,
        },
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    # Step 6: Agent retries DANGEROUS tool with approved token -> Policy ALLOW -> Executes!
    async with session_factory() as session:
        dangerous_result = await registry.execute_tool(
            server_id=server_id,
            tool_name="mock_dangerous_push",
            arguments={"branch": "devaura/fix-42"},
            user_id="usr_developer_01",
            approval_token=approval_token,
            session=session,
        )
        await session.commit()
        assert not dangerous_result.is_error
        assert "Successfully pushed branch" in dangerous_result.content

    # Step 7: Replay attack prevention: Token has been consumed and cannot be reused
    with pytest.raises(MCPApprovalRequiredError):
        async with session_factory() as session:
            await registry.execute_tool(
                server_id=server_id,
                tool_name="mock_dangerous_push",
                arguments={"branch": "devaura/fix-42"},
                approval_token=approval_token,
                session=session,
            )


@pytest.mark.asyncio
async def test_mcp_api_execute_and_approval_route(client: AsyncClient):
    # Test execution route via FastAPI
    exec_res = await client.post(
        "/api/v1/mcp/servers/srv_devaura_native/tools/read_file/execute",
        json={
            "arguments": {"path": "README.md", "start_line": 1, "end_line": 5},
        },
    )
    assert exec_res.status_code == 200
    body = exec_res.json()
    assert body["status"] == "success"
    assert "Devaura" in body["content"]
