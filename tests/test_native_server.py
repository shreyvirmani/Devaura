import json
import pytest
from mcp.policy.policy_engine import PathSecurityViolation
from mcp.server.devaura_server import get_native_mcp_server


@pytest.mark.asyncio
async def test_native_server_read_file():
    server = get_native_mcp_server()
    res = await server.call_tool("read_file", {"path": "README.md", "start_line": 1, "end_line": 10})
    content = res.content[0].text
    assert "Devaura" in content
    assert "1:" in content


@pytest.mark.asyncio
async def test_native_server_read_file_path_traversal():
    server = get_native_mcp_server()
    res = await server.call_tool("read_file", {"path": "../../etc/passwd"})
    content = res.content[0].text
    assert "Security Violation" in content or "rejected" in content


@pytest.mark.asyncio
async def test_native_server_search_code():
    server = get_native_mcp_server()
    res = await server.call_tool("search_code", {"query": "DevauraMCPClient", "max_results": 5})
    content = res.content[0].text
    assert "mcp_client.py" in content


@pytest.mark.asyncio
async def test_native_server_git_history():
    server = get_native_mcp_server()
    res = await server.call_tool("git_history", {"limit": 3})
    content = res.content[0].text
    assert len(content.strip()) > 0
    # Must contain commit hash
    assert any(c in content for c in ["feat", "docs"])


@pytest.mark.asyncio
async def test_native_server_inspect_diff():
    server = get_native_mcp_server()
    res = await server.call_tool("inspect_diff", {})
    content = res.content[0].text
    # Should either report no uncommitted diff or sanitized diff
    assert "diff" in content.lower() or "no uncommitted" in content.lower()


@pytest.mark.asyncio
async def test_native_server_analyze_repository():
    server = get_native_mcp_server()
    res = await server.call_tool("analyze_repository", {"workspace": "."})
    content = res.content[0].text
    data = json.loads(content)
    assert "Python" in data["languages"]
    assert "pip/poetry" in data["package_managers"]
    assert "pytest" in data["test_frameworks"]


@pytest.mark.asyncio
async def test_native_server_find_related_tests():
    server = get_native_mcp_server()
    res = await server.call_tool("find_related_tests", {"target_file": "policy_engine.py"})
    content = res.content[0].text
    assert "test_policy_engine.py" in content
