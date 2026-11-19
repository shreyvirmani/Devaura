from pathlib import Path
import pytest
from code_intelligence.indexer.file_indexer import FileIndexer
from code_intelligence.search.path_search import PathSearch
from code_intelligence.search.ripgrep_search import RipgrepSearch
from code_intelligence.search.search_coordinator import MultiTierSearchCoordinator
from code_intelligence.search.symbol_search import SymbolSearch

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fixture_repo"


def test_ripgrep_search():
    searcher = RipgrepSearch(workspace_root=FIXTURE_PATH)
    matches = searcher.search(query="divide by zero", max_results=5)

    assert len(matches) > 0
    match_files = [m.file for m in matches]
    assert any("core.py" in f for f in match_files)
    assert matches[0].tier == "ripgrep"


def test_symbol_search_in_memory():
    indexer = FileIndexer(workspace_root=FIXTURE_PATH)
    parsed_files = indexer.index_workspace()

    sym_search = SymbolSearch()
    matches = sym_search.search_parsed_files(parsed_files, query="Calculator")

    assert len(matches) >= 2
    sym_names = [m.symbol_name for m in matches]
    assert "Calculator" in sym_names
    assert "ScientificCalculator" in sym_names


def test_path_search():
    searcher = PathSearch(workspace_root=FIXTURE_PATH)
    matches = searcher.search(query="advanced", max_results=5)

    assert len(matches) >= 1
    match_files = [m.file for m in matches]
    assert any("advanced.py" in f for f in match_files)


@pytest.mark.asyncio
async def test_multi_tier_search_coordinator():
    coord = MultiTierSearchCoordinator(workspace_root=FIXTURE_PATH)
    response = await coord.execute_search(query="CalculationError", tier="all", max_results=10)

    assert response.total_matches > 0
    assert any("utils.py" in m.file for m in response.matches)
