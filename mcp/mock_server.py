import json
from mcp.models import RiskLevel
from mcp.server.mcpserver import MCPServer


def create_mock_mcp_server(name: str = "mock-mcp-server") -> MCPServer:
    """Create a deterministic Mock MCP Server for testing."""
    server = MCPServer(
        name=name,
        version="1.0.0",
        instructions="Deterministic mock MCP server for testing Devaura MCP Client, Registry and Policy Engine.",
    )

    @server.tool(name="mock_get_issue", description="Fetches mock issue data.")
    async def mock_get_issue(issue_id: int) -> str:
        return json.dumps(
            {
                "id": issue_id,
                "title": f"Mock Issue #{issue_id}: Authentication header error",
                "body": "Incoming request token raises IndexError in auth middleware.",
                "labels": ["bug", "auth"],
            }
        )
    mock_get_issue.risk_level = RiskLevel.SAFE

    @server.tool(name="mock_search_code", description="Simulated code search.")
    async def mock_search_code(query: str, path: str = ".") -> str:
        return json.dumps(
            [
                {"file": "src/auth.py", "line": 42, "match": f"matches query '{query}'"},
                {"file": "tests/test_auth.py", "line": 15, "match": f"tests query '{query}'"},
            ]
        )
    mock_search_code.risk_level = RiskLevel.SAFE

    @server.tool(name="mock_read_file", description="Simulated file reading.")
    async def mock_read_file(path: str) -> str:
        return f"# File contents for {path}\ndef mock_function():\n    return True\n"
    mock_read_file.risk_level = RiskLevel.SAFE

    @server.tool(name="mock_run_tests", description="Simulated test execution.")
    async def mock_run_tests(command: str = "pytest") -> str:
        return json.dumps(
            {
                "command": command,
                "status": "passed",
                "passed": 12,
                "failed": 0,
                "duration_seconds": 1.25,
            }
        )
    mock_run_tests.risk_level = RiskLevel.CONTROLLED

    @server.tool(name="mock_dangerous_push", description="Dangerous mock remote push.")
    async def mock_dangerous_push(branch: str) -> str:
        return f"Successfully pushed branch '{branch}' to origin remote."
    mock_dangerous_push.risk_level = RiskLevel.DANGEROUS

    # Mock Resource
    @server.resource(uri="mock://issue/42", name="Mock Issue 42 Resource")
    async def mock_issue_resource() -> str:
        return "Resource data for issue 42"

    # Mock Prompt
    @server.prompt(name="mock_prompt", description="Mock prompt template")
    async def mock_prompt(arg1: str) -> str:
        return f"Mock prompt rendered with argument: {arg1}"

    return server
