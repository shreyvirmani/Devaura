import pytest
from mcp.client.mcp_client import DevauraMCPClient
from mcp.mock_server import create_mock_mcp_server
from mcp.models import MCPServerInfo, RiskLevel, TransportType


@pytest.fixture
def mock_client():
    mock_server = create_mock_mcp_server()
    info = MCPServerInfo(
        id="srv_test_mock",
        name="Test Mock Server",
        transport=TransportType.NATIVE,
        endpoint="internal://mock",
        status="disconnected",
    )
    client = DevauraMCPClient(info, native_server_instance=mock_server)
    return client


@pytest.mark.asyncio
async def test_mcp_client_connection_and_discovery(mock_client: DevauraMCPClient):
    assert not mock_client.is_connected
    await mock_client.connect()
    assert mock_client.is_connected
    assert mock_client.server_info.status == "connected"

    # Tool discovery
    tools = await mock_client.list_tools()
    tool_names = [t.name for t in tools]
    assert "mock_get_issue" in tool_names
    assert "mock_search_code" in tool_names
    assert "mock_read_file" in tool_names
    assert "mock_run_tests" in tool_names
    assert "mock_dangerous_push" in tool_names

    # Resource discovery
    resources = await mock_client.list_resources()
    assert len(resources) >= 1
    assert any("42" in r.uri for r in resources)

    # Prompt discovery
    prompts = await mock_client.list_prompts()
    assert len(prompts) >= 1
    assert any(p.name == "mock_prompt" for p in prompts)

    # Cleanup
    await mock_client.disconnect()
    assert not mock_client.is_connected


@pytest.mark.asyncio
async def test_mcp_client_tool_execution(mock_client: DevauraMCPClient):
    await mock_client.connect()

    result = await mock_client.call_tool("mock_get_issue", {"issue_id": 42})
    assert not result.is_error
    assert "Mock Issue #42" in result.content
    assert result.latency_ms > 0 or result.latency_ms == 0.0

    await mock_client.disconnect()


@pytest.mark.asyncio
async def test_mcp_client_read_resource_and_get_prompt(mock_client: DevauraMCPClient):
    await mock_client.connect()

    res_content = await mock_client.read_resource("mock://issue/42")
    assert "issue 42" in res_content.lower()

    prompt_data = await mock_client.get_prompt("mock_prompt", {"arg1": "test-context"})
    assert "test-context" in str(prompt_data)

    await mock_client.disconnect()
