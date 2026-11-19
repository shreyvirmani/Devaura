import uuid
from typing import Dict, List, Optional, Set
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from code_intelligence.graph.repository_graph import RepositoryGraph
from code_intelligence.models import ParsedFile
from database.models.code_intelligence import (
    CodeFile,
    CodeImport,
    CodeRelationship,
    CodeSymbol,
    CodeTestMapping,
)


class SymbolIndexer:
    """Persists parsed files, symbols, imports, and relationships to the relational database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def persist_index_data(
        self,
        repository_id: str,
        parsed_files: List[ParsedFile],
        graph: Optional[RepositoryGraph] = None,
        test_mappings: Optional[List[dict]] = None,
        incremental: bool = False,
    ) -> Dict[str, int]:
        """Saves all extracted intelligence into the database with incremental deletion handling."""
        stats = {
            "files_indexed": 0,
            "symbols_indexed": 0,
            "relationships_indexed": 0,
            "imports_indexed": 0,
            "deleted_files": 0,
        }

        # If not incremental, clear previous index for this repository
        if not incremental:
            await self._clear_repository_index(repository_id)

        file_id_map: Dict[str, str] = {}  # file_path -> db_file_id
        symbol_id_map: Dict[str, str] = {}  # f"{file_path}:{qualname}" -> db_symbol_id

        # In incremental mode, handle deleted files
        current_disk_paths: Set[str] = {pf.path for pf in parsed_files}
        if incremental:
            existing_files_res = await self.session.execute(
                select(CodeFile).where(CodeFile.repository_id == repository_id)
            )
            existing_db_files = existing_files_res.scalars().all()
            for db_f in existing_db_files:
                if db_f.path not in current_disk_paths:
                    await self.session.execute(delete(CodeTestMapping).where(
                        (CodeTestMapping.source_file_id == db_f.id) | (CodeTestMapping.test_file_id == db_f.id)
                    ))
                    await self.session.execute(delete(CodeFile).where(CodeFile.id == db_f.id))
                    stats["deleted_files"] += 1

        # 1. Persist CodeFile and CodeImport records
        for pf in parsed_files:
            # Check existing file if incremental
            file_record = None
            if incremental:
                res = await self.session.execute(
                    select(CodeFile).where(
                        CodeFile.repository_id == repository_id,
                        CodeFile.path == pf.path,
                    )
                )
                file_record = res.scalars().first()

            if file_record:
                if file_record.hash == pf.hash:
                    # Unchanged file in incremental mode
                    file_id_map[pf.path] = file_record.id
                    # Populate symbol_id_map for existing unchanged symbols
                    sym_res = await self.session.execute(
                        select(CodeSymbol).where(CodeSymbol.file_id == file_record.id)
                    )
                    for s in sym_res.scalars().all():
                        symbol_id_map[f"{pf.path}:{s.qualified_name}"] = s.id
                        symbol_id_map[f"{pf.path}:{s.name}"] = s.id
                    continue

                # Update existing file record
                file_record.hash = pf.hash
                file_record.size_bytes = pf.size_bytes
                file_record.line_count = pf.line_count
                db_file_id = file_record.id
                # Remove stale symbols & imports for this modified file
                await self.session.execute(delete(CodeSymbol).where(CodeSymbol.file_id == db_file_id))
                await self.session.execute(delete(CodeImport).where(CodeImport.file_id == db_file_id))
            else:
                db_file_id = str(uuid.uuid4())
                file_record = CodeFile(
                    id=db_file_id,
                    repository_id=repository_id,
                    path=pf.path,
                    language=pf.language,
                    hash=pf.hash,
                    size_bytes=pf.size_bytes,
                    line_count=pf.line_count,
                )
                self.session.add(file_record)

            file_id_map[pf.path] = db_file_id
            stats["files_indexed"] += 1

            # Save imports
            for imp in pf.imports:
                import_rec = CodeImport(
                    file_id=db_file_id,
                    module=imp.module,
                    symbol_name=imp.symbol_name,
                    alias=imp.alias,
                    is_external=imp.is_external,
                    line_number=imp.line_number,
                )
                self.session.add(import_rec)
                stats["imports_indexed"] += 1

            # Save top-level symbols first, then children
            top_level_syms = [s for s in pf.symbols if not s.parent_name]
            nested_syms = [s for s in pf.symbols if s.parent_name]

            for s in top_level_syms:
                sym_id = str(uuid.uuid4())
                sym_rec = CodeSymbol(
                    id=sym_id,
                    file_id=db_file_id,
                    repository_id=repository_id,
                    name=s.name,
                    qualified_name=s.qualified_name,
                    kind=s.kind.value,
                    start_line=s.start_line,
                    end_line=s.end_line,
                    signature=s.signature,
                    docstring=s.docstring,
                    parent_symbol_id=None,
                    metadata_json=s.metadata,
                )
                self.session.add(sym_rec)
                symbol_id_map[f"{pf.path}:{s.qualified_name}"] = sym_id
                symbol_id_map[f"{pf.path}:{s.name}"] = sym_id
                stats["symbols_indexed"] += 1

            for s in nested_syms:
                sym_id = str(uuid.uuid4())
                parent_id = symbol_id_map.get(f"{pf.path}:{s.parent_name}")
                sym_rec = CodeSymbol(
                    id=sym_id,
                    file_id=db_file_id,
                    repository_id=repository_id,
                    name=s.name,
                    qualified_name=s.qualified_name,
                    kind=s.kind.value,
                    start_line=s.start_line,
                    end_line=s.end_line,
                    signature=s.signature,
                    docstring=s.docstring,
                    parent_symbol_id=parent_id,
                    metadata_json=s.metadata,
                )
                self.session.add(sym_rec)
                symbol_id_map[f"{pf.path}:{s.qualified_name}"] = sym_id
                symbol_id_map[f"{pf.path}:{s.name}"] = sym_id
                stats["symbols_indexed"] += 1

        # 2. Persist Graph Edges as CodeRelationship records
        if graph:
            # Refresh relationships for repository
            await self.session.execute(delete(CodeRelationship).where(CodeRelationship.repository_id == repository_id))
            for edge in graph.edges:
                rel_meta = dict(edge.metadata or {})
                if edge.evidence:
                    rel_meta["evidence"] = edge.evidence
                if edge.source_location:
                    rel_meta["source_location"] = edge.source_location

                rel_rec = CodeRelationship(
                    repository_id=repository_id,
                    source_type="symbol" if "symbol:" in edge.source_id else "file",
                    source_id=edge.source_id,
                    target_type="symbol" if "symbol:" in edge.target_id else ("file" if "file:" in edge.target_id else "module"),
                    target_id=edge.target_id,
                    relationship_type=edge.type,
                    confidence=edge.confidence,
                    resolution_status=edge.resolution_status,
                    metadata_json=rel_meta,
                )
                self.session.add(rel_rec)
                stats["relationships_indexed"] += 1

        # 3. Persist Test Mappings
        if test_mappings:
            await self.session.execute(delete(CodeTestMapping).where(CodeTestMapping.repository_id == repository_id))
            for tm in test_mappings:
                test_fid = file_id_map.get(tm.get("test_file"))
                src_fid = file_id_map.get(tm.get("source_file"))
                if test_fid and src_fid:
                    tm_rec = CodeTestMapping(
                        repository_id=repository_id,
                        source_file_id=src_fid,
                        test_file_id=test_fid,
                        confidence=tm.get("confidence", 0.9),
                        relationship_type="TESTS_FILE",
                    )
                    self.session.add(tm_rec)

        await self.session.commit()
        return stats

    async def _clear_repository_index(self, repository_id: str) -> None:
        """Purges existing indexed code intelligence for repository."""
        await self.session.execute(delete(CodeTestMapping).where(CodeTestMapping.repository_id == repository_id))
        await self.session.execute(delete(CodeRelationship).where(CodeRelationship.repository_id == repository_id))
        await self.session.execute(delete(CodeSymbol).where(CodeSymbol.repository_id == repository_id))
        await self.session.execute(delete(CodeImport).where(CodeImport.file_id.in_(
            select(CodeFile.id).where(CodeFile.repository_id == repository_id)
        )))
        await self.session.execute(delete(CodeFile).where(CodeFile.repository_id == repository_id))
        await self.session.commit()
