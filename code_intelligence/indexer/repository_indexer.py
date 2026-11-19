import time
import uuid
from pathlib import Path
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.logger import logger
from code_intelligence.graph.relationship_builder import RelationshipBuilder
from code_intelligence.graph.repository_graph import RepositoryGraph
from code_intelligence.indexer.file_indexer import FileIndexer
from code_intelligence.indexer.symbol_indexer import SymbolIndexer
from code_intelligence.models import IndexRepositoryResponse
from code_intelligence.tests.test_relationships import TestRelationshipsEngine
from database.models.code_intelligence import CodeIndexRun, IndexStatus
from database.models.models import Repository


class RepositoryIndexer:
    """Full and incremental indexing pipeline for repositories."""

    def __init__(self, workspace_root: Path | str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.file_indexer = FileIndexer(self.workspace_root)
        self.test_engine = TestRelationshipsEngine(self.workspace_root)

    async def index_repository(
        self,
        repository_id: Optional[str] = None,
        path_filter: Optional[str] = None,
        force_full: bool = False,
        session: Optional[AsyncSession] = None,
    ) -> IndexRepositoryResponse:
        start_time = time.time()
        rep_id = repository_id or "local-workspace"

        logger.info(
            f"Starting repository indexing for '{rep_id}' at '{self.workspace_root}' (force_full={force_full})",
            extra={"component": "repository_indexer", "event": "start", "repo_id": rep_id},
        )

        try:
            # 1. Parse all workspace source files
            parsed_files = self.file_indexer.index_workspace(path_filter=path_filter)

            # 2. Build semantic relationship graph
            rel_builder = RelationshipBuilder(repository_id=rep_id)
            graph = rel_builder.build_graph(parsed_files)

            # 3. Discover test mappings
            test_mappings = self.test_engine.discover_test_mappings(parsed_files)

            symbols_count = sum(len(pf.symbols) for pf in parsed_files)
            files_count = len(parsed_files)

            # 4. Persist to DB if database session is provided
            if session:
                symbol_indexer = SymbolIndexer(session)
                await symbol_indexer.persist_index_data(
                    repository_id=rep_id,
                    parsed_files=parsed_files,
                    graph=graph,
                    test_mappings=test_mappings,
                    incremental=not force_full,
                )

                # Record index run
                duration_ms = round((time.time() - start_time) * 1000.0, 2)
                run_rec = CodeIndexRun(
                    id=str(uuid.uuid4()),
                    repository_id=rep_id,
                    status=IndexStatus.READY.value,
                    files_indexed=files_count,
                    symbols_indexed=symbols_count,
                    duration_ms=duration_ms,
                )
                session.add(run_rec)
                await session.commit()
            else:
                duration_ms = round((time.time() - start_time) * 1000.0, 2)

            logger.info(
                f"Repository indexing completed: {files_count} files, {symbols_count} symbols ({duration_ms}ms)",
                extra={"component": "repository_indexer", "event": "finish", "repo_id": rep_id, "duration_ms": duration_ms},
            )

            return IndexRepositoryResponse(
                repository_id=rep_id,
                status=IndexStatus.READY.value,
                files_indexed=files_count,
                symbols_indexed=symbols_count,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000.0, 2)
            err_msg = str(e)
            logger.error(
                f"Indexing failed for '{rep_id}': {err_msg}",
                extra={"component": "repository_indexer", "event": "error", "error": err_msg},
            )
            if session:
                try:
                    run_rec = CodeIndexRun(
                        id=str(uuid.uuid4()),
                        repository_id=rep_id,
                        status=IndexStatus.FAILED.value,
                        files_indexed=0,
                        symbols_indexed=0,
                        duration_ms=duration_ms,
                        error_message=err_msg,
                    )
                    session.add(run_rec)
                    await session.commit()
                except Exception:
                    pass

            return IndexRepositoryResponse(
                repository_id=rep_id,
                status=IndexStatus.FAILED.value,
                files_indexed=0,
                symbols_indexed=0,
                duration_ms=duration_ms,
                error_message=err_msg,
            )
