import json
from pathlib import Path
import httpx
import pytest
from apps.api.main import app
from database.connection import init_db
from mcp.server.devaura_server import get_native_mcp_server

FIXTURE_PATH = str((Path(__file__).parent / "fixtures" / "fixture_repo").resolve()).replace("\\", "/")


@pytest.mark.asyncio
async def test_native_mcp_code_intelligence_tools():
    server = get_native_mcp_server()

    # 1. index_repository
    idx_res = await server.call_tool("index_repository", {"workspace": FIXTURE_PATH, "force_full": True})
    idx_data = json.loads(idx_res.content[0].text)
    assert idx_data["status"] == "READY"
    assert idx_data["files_indexed"] >= 5
    assert idx_data["symbols_indexed"] >= 8

    # 2. search_symbol
    sym_res = await server.call_tool("search_symbol", {"query": "power", "workspace": FIXTURE_PATH})
    sym_data = json.loads(sym_res.content[0].text)
    assert any(s["symbol"] == "power" for s in sym_data)

    # 3. get_symbol
    detail_res = await server.call_tool("get_symbol", {"name": "ScientificCalculator", "workspace": FIXTURE_PATH})
    detail_data = json.loads(detail_res.content[0].text)
    assert detail_data["name"] == "ScientificCalculator"
    assert "Calculator" in detail_data["extends"]

    # 4. get_relationships
    rel_res = await server.call_tool("get_relationships", {"target": "calculator/advanced.py", "workspace": FIXTURE_PATH})
    rel_data = json.loads(rel_res.content[0].text)
    assert "target_file" in rel_data

    # 5. get_repository_graph
    graph_res = await server.call_tool("get_repository_graph", {"workspace": FIXTURE_PATH})
    graph_data = json.loads(graph_res.content[0].text)
    assert len(graph_data["nodes"]) > 0
    assert len(graph_data["edges"]) > 0

    # 6. find_related_tests with AST intelligence
    test_res = await server.call_tool("find_related_tests", {"target_file": "calculator/core.py", "workspace": FIXTURE_PATH})
    test_data = json.loads(test_res.content[0].text)
    assert any("test_calculator.py" in t for t in test_data["related_tests"])


@pytest.mark.asyncio
async def test_code_intelligence_api_endpoints():
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger Index
        index_payload = {
            "repository_id": "test-api-repo",
            "workspace": FIXTURE_PATH,
            "force_full": True,
        }
        res = await client.post("/api/v1/code-intelligence/index", json=index_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "READY"
        assert data["files_indexed"] >= 5

        # 2. Status
        res_status = await client.get("/api/v1/code-intelligence/status/test-api-repo")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["files_indexed"] >= 5
        assert status_data["symbols_indexed"] >= 8

        # 3. Files
        res_files = await client.get("/api/v1/code-intelligence/files/test-api-repo")
        assert res_files.status_code == 200
        files_data = res_files.json()
        assert len(files_data) >= 5

        # 4. Symbols
        res_syms = await client.get("/api/v1/code-intelligence/symbols/test-api-repo?kind=class")
        assert res_syms.status_code == 200
        syms_data = res_syms.json()
        class_names = [s["name"] for s in syms_data]
        assert "Calculator" in class_names

        # 5. Multi-tier Search
        search_payload = {
            "query": "Calculator",
            "workspace": FIXTURE_PATH,
            "repository_id": "test-api-repo",
            "tier": "all",
            "max_results": 10,
        }
        res_search = await client.post("/api/v1/code-intelligence/search", json=search_payload)
        assert res_search.status_code == 200
        search_data = res_search.json()
        assert search_data["total_matches"] > 0

        # 6. Graph
        res_graph = await client.get("/api/v1/code-intelligence/graph/test-api-repo")
        assert res_graph.status_code == 200
        g_data = res_graph.json()
        assert len(g_data["nodes"]) > 0

        # 7. Tests mapping
        res_tests = await client.get("/api/v1/code-intelligence/tests/test-api-repo")
        assert res_tests.status_code == 200
        t_data = res_tests.json()
        assert len(t_data) >= 1

        # 8. Git History
        res_git = await client.get("/api/v1/code-intelligence/git/history?limit=5")
        assert res_git.status_code == 200
        assert isinstance(res_git.json(), list)
