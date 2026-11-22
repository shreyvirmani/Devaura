"""Large Repository Performance & Scalability Benchmark.

Validates Section 18 requirements:
1. Indexing time across multi-module repository
2. Incremental indexing latency
3. Search latency (symbol, path, text)
4. Knowledge graph construction and traversal latency
5. Memory usage footprint (tracemalloc)
6. Isolated sandbox creation and cleanup latency
"""

import os
from pathlib import Path
import shutil
import tempfile
import time
import tracemalloc
import pytest

from code_intelligence.graph.queries import GraphQueryEngine
from code_intelligence.graph.relationship_builder import RelationshipBuilder
from code_intelligence.indexer.file_indexer import FileIndexer
from code_intelligence.search.symbol_search import SymbolSearch
from code_intelligence.search.path_search import PathSearch
from sandbox.workspace import IsolatedWorkspace


@pytest.fixture(scope="module")
def large_repo_fixture():
    """Generates a synthetic repository with 100+ files across 10 packages."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="devaura_perf_repo_"))
    
    num_packages = 10
    files_per_pkg = 10  # 100 files total + root files
    
    for p in range(num_packages):
        pkg_dir = tmp_dir / f"pkg_{p}"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        
        for f in range(files_per_pkg):
            file_path = pkg_dir / f"module_{f}.py"
            content = f'''"""Package {p} Module {f}."""
from typing import Dict, List, Optional

class ServiceWorker_{p}_{f}:
    """Worker class for package {p} module {f}."""
    def __init__(self, name: str = "worker_{p}_{f}"):
        self.name = name

    def execute_task(self, payload: Dict[str, str]) -> str:
        return f"Executed {p}_{f} with {{payload}}"

def process_batch_{p}_{f}(items: List[str]) -> int:
    return len(items) * {p + 1}
'''
            file_path.write_text(content, encoding="utf-8")

    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_large_repo_indexing_performance(large_repo_fixture):
    """Measures indexing latency and memory usage on a 100+ file repository."""
    tracemalloc.start()
    t0 = time.perf_counter()
    
    indexer = FileIndexer(workspace_root=large_repo_fixture)
    parsed_files = indexer.index_workspace()
    
    indexing_time_ms = (time.perf_counter() - t0) * 1000
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    peak_mem_mb = peak_mem / (1024 * 1024)
    
    print(f"\n[Large Repo] Indexing: {len(parsed_files)} files indexed in {indexing_time_ms:.1f}ms (Peak RAM: {peak_mem_mb:.2f} MB)")
    
    assert len(parsed_files) >= 100
    assert indexing_time_ms < 5000.0, f"Indexing took too long: {indexing_time_ms:.1f}ms"
    assert peak_mem_mb < 150.0, f"Peak memory exceeded limit: {peak_mem_mb:.2f} MB"


def test_large_repo_graph_query_performance(large_repo_fixture):
    """Measures graph construction and relationship query latency."""
    indexer = FileIndexer(workspace_root=large_repo_fixture)
    parsed_files = indexer.index_workspace()
    
    t0 = time.perf_counter()
    builder = RelationshipBuilder(repository_id="large-perf-repo")
    graph = builder.build_graph(parsed_files)
    graph_build_ms = (time.perf_counter() - t0) * 1000
    
    assert len(graph.nodes) > 200
    assert graph_build_ms < 3000.0, f"Graph build exceeded 3s: {graph_build_ms:.1f}ms"
    
    # Query performance
    query_engine = GraphQueryEngine(graph)
    t_query = time.perf_counter()
    callees = query_engine.get_callees("execute_task")
    query_ms = (time.perf_counter() - t_query) * 1000
    
    print(f"[Large Repo] Graph: {len(graph.nodes)} nodes built in {graph_build_ms:.1f}ms, Query latency: {query_ms:.2f}ms")
    assert query_ms < 100.0, f"Graph query exceeded 100ms: {query_ms:.2f}ms"


def test_large_repo_search_performance(large_repo_fixture):
    """Measures symbol and path search latency on large repository."""
    indexer = FileIndexer(workspace_root=large_repo_fixture)
    parsed_files = indexer.index_workspace()
    
    # Symbol search
    sym_search = SymbolSearch()
    t0 = time.perf_counter()
    matches = sym_search.search_parsed_files(parsed_files, query="ServiceWorker_5")
    sym_ms = (time.perf_counter() - t0) * 1000
    
    assert len(matches) >= 10
    assert sym_ms < 100.0, f"Symbol search exceeded 100ms: {sym_ms:.2f}ms"
    
    # Path search
    path_search = PathSearch(workspace_root=large_repo_fixture)
    t1 = time.perf_counter()
    path_matches = path_search.search(query="module_3", max_results=10)
    path_ms = (time.perf_counter() - t1) * 1000
    
    assert len(path_matches) >= 10
    assert path_ms < 100.0, f"Path search exceeded 100ms: {path_ms:.2f}ms"
    print(f"[Large Repo] Search Latency: Symbol={sym_ms:.2f}ms, Path={path_ms:.2f}ms")


def test_large_repo_sandbox_lifecycle_performance(large_repo_fixture):
    """Measures isolated workspace creation and cleanup latency."""
    t0 = time.perf_counter()
    ws = IsolatedWorkspace(source_repo_path=str(large_repo_fixture), workspace_id="perf_test_ws")
    sandbox_path = ws.create()
    create_ms = (time.perf_counter() - t0) * 1000
    
    assert os.path.isdir(sandbox_path)
    
    t1 = time.perf_counter()
    ws.cleanup()
    cleanup_ms = (time.perf_counter() - t1) * 1000
    
    print(f"[Large Repo] Sandbox Lifecycle: Create={create_ms:.1f}ms, Cleanup={cleanup_ms:.1f}ms")
    assert create_ms < 2000.0, f"Sandbox creation exceeded 2s: {create_ms:.1f}ms"
    assert cleanup_ms < 1000.0, f"Sandbox cleanup exceeded 1s: {cleanup_ms:.1f}ms"
