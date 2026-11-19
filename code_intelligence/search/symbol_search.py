from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from code_intelligence.models import ParsedFile, SearchMatch
from database.models.code_intelligence import CodeFile, CodeSymbol


class SymbolSearch:
    """Tier 2: Symbol-aware search querying indexed symbols by name, kind, or qualified name."""

    async def search_db(
        self,
        session: AsyncSession,
        query: str,
        repository_id: Optional[str] = None,
        kind: Optional[str] = None,
        max_results: int = 25,
    ) -> List[SearchMatch]:
        """Queries CodeSymbol records from the database."""
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        stmt = (
            select(CodeSymbol, CodeFile.path)
            .join(CodeFile, CodeSymbol.file_id == CodeFile.id)
            .limit(max_results)
        )

        filters = []
        if repository_id:
            filters.append(CodeSymbol.repository_id == repository_id)

        # Name or qualified name match
        pattern = f"%{clean_query}%"
        filters.append(
            or_(
                CodeSymbol.name.ilike(pattern),
                CodeSymbol.qualified_name.ilike(pattern),
            )
        )

        if kind:
            filters.append(CodeSymbol.kind == kind.lower())

        stmt = stmt.where(*filters)
        result = await session.execute(stmt)
        rows = result.all()

        matches: List[SearchMatch] = []
        for symbol, file_path in rows:
            # Score exact name match higher than substring
            score = 1.0 if symbol.name.lower() == clean_query.lower() else 0.8
            matches.append(
                SearchMatch(
                    tier="symbol",
                    file=file_path,
                    line=symbol.start_line,
                    column=1,
                    text=symbol.signature or f"{symbol.kind} {symbol.qualified_name}",
                    symbol_name=symbol.name,
                    kind=symbol.kind,
                    score=score,
                )
            )

        return sorted(matches, key=lambda m: m.score, reverse=True)

    def search_parsed_files(
        self,
        parsed_files: List[ParsedFile],
        query: str,
        kind: Optional[str] = None,
        max_results: int = 25,
    ) -> List[SearchMatch]:
        """In-memory symbol search against parsed file structures."""
        if not query or not query.strip():
            return []

        clean_query = query.strip().lower()
        matches: List[SearchMatch] = []

        for pf in parsed_files:
            for sym in pf.symbols:
                if kind and sym.kind.value.lower() != kind.lower():
                    continue

                sym_name_lower = sym.name.lower()
                qual_lower = sym.qualified_name.lower()

                if clean_query in sym_name_lower or clean_query in qual_lower:
                    score = 1.0 if sym_name_lower == clean_query else 0.8
                    matches.append(
                        SearchMatch(
                            tier="symbol",
                            file=pf.path,
                            line=sym.start_line,
                            column=1,
                            text=sym.signature or f"{sym.kind.value} {sym.qualified_name}",
                            symbol_name=sym.name,
                            kind=sym.kind.value,
                            score=score,
                        )
                    )
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        return sorted(matches, key=lambda m: m.score, reverse=True)
