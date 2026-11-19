from pathlib import Path
import pytest
from code_intelligence.graph.queries import GraphQueryEngine
from code_intelligence.graph.relationship_builder import RelationshipBuilder
from code_intelligence.indexer.file_indexer import FileIndexer
from code_intelligence.indexer.repository_indexer import RepositoryIndexer
from code_intelligence.tests.test_relationships import TestRelationshipsEngine

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fixture_repo"


def test_file_indexer_workspace_scan():
    indexer = FileIndexer(workspace_root=FIXTURE_PATH)
    discovered = indexer.scan_workspace()
    filenames = [p.name for p in discovered]

    assert "core.py" in filenames
    assert "advanced.py" in filenames
    assert "utils.py" in filenames
    assert "test_calculator.py" in filenames
    assert "test_advanced.py" in filenames


def test_relationship_graph_construction():
    indexer = FileIndexer(workspace_root=FIXTURE_PATH)
    parsed_files = indexer.index_workspace()

    builder = RelationshipBuilder(repository_id="fixture-repo")
    graph = builder.build_graph(parsed_files)

    assert len(graph.nodes) > 10
    assert len(graph.edges) > 5

    edge_types = {e.type for e in graph.edges}
    assert "CONTAINS" in edge_types
    assert "DEFINES" in edge_types
    assert "IMPORTS" in edge_types
    assert "CALLS" in edge_types
    assert "EXTENDS" in edge_types
    assert "TESTS" in edge_types

    # Verify query engine
    query_engine = GraphQueryEngine(graph)
    callees = query_engine.get_callees("add")
    callee_labels = [c.label for c in callees]
    assert "_validate_number" in callee_labels or "format_result" in callee_labels

    callers = query_engine.get_callers("_validate_number")
    assert len(callers) > 0

    blast_radius = query_engine.get_blast_radius("symbol:calculator/utils.py:format_result")
    assert blast_radius["total_impacted"] >= 1


def test_test_relationships_engine():
    indexer = FileIndexer(workspace_root=FIXTURE_PATH)
    parsed_files = indexer.index_workspace()

    engine = TestRelationshipsEngine(workspace_root=FIXTURE_PATH)
    mappings = engine.discover_test_mappings(parsed_files)

    assert len(mappings) >= 2
    mapped_sources = [m["source_file"] for m in mappings]
    mapped_tests = [m["test_file"] for m in mappings]

    assert any("advanced.py" in s for s in mapped_sources)
    assert any("test_advanced.py" in t for t in mapped_tests)


@pytest.mark.asyncio
async def test_repository_indexer_standalone():
    indexer = RepositoryIndexer(workspace_root=FIXTURE_PATH)
    res = await indexer.index_repository(repository_id="test-run")

    assert res.status == "READY"
    assert res.files_indexed >= 5
    assert res.symbols_indexed >= 8
    assert res.duration_ms > 0
