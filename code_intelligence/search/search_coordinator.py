from pathlib import Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from code_intelligence.models import CodeSearchResponse, SearchMatch
from code_intelligence.search.path_search import PathSearch
from code_intelligence.search.ripgrep_search import RipgrepSearch
from code_intelligence.search.semantic_search import SemanticSearch
from code_intelligence.search.symbol_search import SymbolSearch


class MultiTierSearchCoordinator:
    """Coordinates search queries across Tier 1 (Ripgrep), Tier 2 (Symbol), Tier 3 (Path), and Tier 4 (Semantic)."""

    def __init__(self, workspace_root: Path | str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.ripgrep_search = RipgrepSearch(self.workspace_root)
        self.symbol_search = SymbolSearch()
        self.path_search = PathSearch(self.workspace_root)
        self.semantic_search = SemanticSearch(is_enabled=False)

    async def execute_search(
        self,
        query: str,
        tier: str = "all",
        path_filter: Optional[str] = None,
        max_results: int = 25,
        case_sensitive: bool = False,
        session: Optional[AsyncSession] = None,
        repository_id: Optional[str] = None,
    ) -> CodeSearchResponse:
        tier = tier.lower()
        collected_matches: List[SearchMatch] = []

        # 1. Tier 2: Symbol Search (checked first if tier is "symbol" or "all")
        if tier in {"symbol", "all"} and session:
            try:
                sym_matches = await self.symbol_search.search_db(
                    session=session,
                    query=query,
                    repository_id=repository_id,
                    max_results=max_results,
                )
                collected_matches.extend(sym_matches)
            except Exception:
                pass

        # 2. Tier 1: Ripgrep Search
        if tier in {"ripgrep", "all"} and len(collected_matches) < max_results:
            rg_remaining = max_results - len(collected_matches)
            rg_matches = self.ripgrep_search.search(
                query=query,
                path_filter=path_filter,
                max_results=rg_remaining,
                case_sensitive=case_sensitive,
            )
            collected_matches.extend(rg_matches)

        # 3. Tier 3: Path Search
        if tier in {"path", "all"} and len(collected_matches) < max_results:
            path_remaining = max_results - len(collected_matches)
            path_matches = self.path_search.search(
                query=query,
                max_results=path_remaining,
            )
            collected_matches.extend(path_matches)

        # 4. Tier 4: Semantic Search
        if tier in {"semantic", "all"} and self.semantic_search.is_enabled:
            sem_matches = self.semantic_search.search(query=query, max_results=5)
            collected_matches.extend(sem_matches)

        # Deduplicate matches by (tier, file, line)
        seen = set()
        deduped: List[SearchMatch] = []
        for m in collected_matches:
            key = (m.tier, m.file, m.line)
            if key not in seen:
                seen.add(key)
                deduped.append(m)

        # Sort by match score descending
        deduped.sort(key=lambda m: m.score, reverse=True)
        final_matches = deduped[:max_results]

        return CodeSearchResponse(
            query=query,
            total_matches=len(final_matches),
            matches=final_matches,
        )
