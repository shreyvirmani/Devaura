import json
from pathlib import Path
import pytest
from code_intelligence.graph.queries import GraphQueryEngine
from code_intelligence.graph.relationship_builder import RelationshipBuilder
from code_intelligence.indexer.file_indexer import FileIndexer
from code_intelligence.indexer.repository_indexer import RepositoryIndexer
from code_intelligence.indexer.symbol_indexer import SymbolIndexer
from database.connection import init_db
from database.models.code_intelligence import CodeFile, IndexStatus
from mcp.server.devaura_server import get_native_mcp_server

VALIDATION_REPO = Path(__file__).parent / "fixtures" / "validation_repo"


@pytest.mark.asyncio
async def test_incremental_indexing_and_staleness(tmp_path):
    # Create temporary repo directory
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    f1 = repo_dir / "mod_a.py"
    f1.write_text("def func_a():\n    return 1\n", encoding="utf-8")

    f2 = repo_dir / "mod_b.py"
    f2.write_text("from mod_a import func_a\ndef func_b():\n    return func_a()\n", encoding="utf-8")

    await init_db()
    from database.connection import get_session_maker
    session_factory = get_session_maker()

    indexer = RepositoryIndexer(workspace_root=repo_dir)

    # 1. First full index
    async with session_factory() as session:
        res1 = await indexer.index_repository(repository_id="test-incr-repo", session=session)
        assert res1.status == IndexStatus.READY.value
        assert res1.files_indexed == 2
        assert res1.symbols_indexed == 2

    # 2. Check staleness - should be READY
    async with session_factory() as session:
        staleness = await indexer.check_index_staleness(repository_id="test-incr-repo", session=session)
        assert staleness == IndexStatus.READY.value

    # 3. Modify mod_b.py
    f2.write_text("from mod_a import func_a\ndef func_b():\n    return func_a() * 2\n", encoding="utf-8")

    # 4. Check staleness - should now be STALE
    async with session_factory() as session:
        staleness2 = await indexer.check_index_staleness(repository_id="test-incr-repo", session=session)
        assert staleness2 == IndexStatus.STALE.value

    # 5. Incremental index
    async with session_factory() as session:
        res2 = await indexer.index_repository(repository_id="test-incr-repo", force_full=False, session=session)
        assert res2.status == IndexStatus.READY.value

    # 6. Delete mod_b.py and run incremental index
    f2.unlink()
    async with session_factory() as session:
        res3 = await indexer.index_repository(repository_id="test-incr-repo", force_full=False, session=session)
        assert res3.status == IndexStatus.READY.value
        assert res3.files_indexed == 1  # Only mod_a.py remaining


def test_bounded_blast_radius():
    file_indexer = FileIndexer(workspace_root=VALIDATION_REPO)
    parsed_files = file_indexer.index_workspace()

    builder = RelationshipBuilder(repository_id="validation-repo")
    graph = builder.build_graph(parsed_files)
    query_engine = GraphQueryEngine(graph)

    # Blast radius for User entity
    blast = query_engine.get_blast_radius("symbol:app/models.py:User", max_depth=3, max_nodes=50)

    assert blast["total_impacted"] > 0
    assert "AdminUser" in blast["affected_symbols"] or "GuestUser" in blast["affected_symbols"]
    assert len(blast["impacted"]) <= 50

    # Ensure every impacted item has reason and confidence
    for item in blast["impacted"]:
        assert "reason" in item
        assert "confidence" in item
        assert item["confidence"] > 0.0


def test_sensitive_files_protection(tmp_path):
    repo_dir = tmp_path / "sensitive_repo"
    repo_dir.mkdir()

    # Normal code
    (repo_dir / "service.py").write_text("def work(): pass\n", encoding="utf-8")

    # Sensitive files
    (repo_dir / ".env").write_text("SECRET_KEY=123456\n", encoding="utf-8")
    (repo_dir / ".env.production").write_text("DB_PASS=admin\n", encoding="utf-8")
    (repo_dir / "server.key").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
    (repo_dir / "cert.pem").write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")

    indexer = FileIndexer(workspace_root=repo_dir)
    discovered = indexer.scan_workspace()
    discovered_names = [p.name for p in discovered]

    assert "service.py" in discovered_names
    assert ".env" not in discovered_names
    assert ".env.production" not in discovered_names
    assert "server.key" not in discovered_names
    assert "cert.pem" not in discovered_names


@pytest.mark.asyncio
async def test_native_mcp_validation_repo():
    server = get_native_mcp_server()
    repo_path = str(VALIDATION_REPO.resolve()).replace("\\", "/")

    # 1. index_repository
    idx_res = await server.call_tool("index_repository", {"workspace": repo_path})
    idx_data = json.loads(idx_res.content[0].text)
    assert idx_data["status"] == "READY"
    assert idx_data["files_indexed"] >= 8

    # 2. search_symbol
    sym_res = await server.call_tool("search_symbol", {"query": "UserProfile", "workspace": repo_path})
    sym_data = json.loads(sym_res.content[0].text)
    assert any(s["symbol"] == "UserProfile" for s in sym_data)

    # 3. get_relationships
    rel_res = await server.call_tool("get_relationships", {"target": "verify_password", "workspace": repo_path})
    rel_data = json.loads(rel_res.content[0].text)
    assert "callees" in rel_data
    assert any("hash_password" in c for c in rel_data["callees"])

    # 4. find_related_tests
    test_res = await server.call_tool("find_related_tests", {"target_file": "app/auth.py", "workspace": repo_path})
    test_data = json.loads(test_res.content[0].text)
    assert any("test_auth.py" in t for t in test_data["related_tests"])
