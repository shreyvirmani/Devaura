import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from code_intelligence.git import GitIntelligence
from code_intelligence.graph import GraphQueryEngine, RelationshipBuilder
from code_intelligence.indexer import FileIndexer, RepositoryIndexer
from code_intelligence.models import (
    CodeSearchRequest,
    CodeSearchResponse,
    GraphEdge,
    GraphNode,
    IndexRepositoryRequest,
    IndexRepositoryResponse,
    RepositoryGraphData,
)
from code_intelligence.search import MultiTierSearchCoordinator
from database.connection import get_db
from database.models.code_intelligence import (
    CodeFile,
    CodeImport,
    CodeIndexRun,
    CodeRelationship,
    CodeSymbol,
    CodeTestMapping,
    IndexStatus,
)
from database.models.models import Repository

router = APIRouter(prefix="/code-intelligence", tags=["Code Intelligence"])


# 1. Trigger Indexing
@router.post("/index", response_model=IndexRepositoryResponse)
async def index_repository_endpoint(
    req: IndexRepositoryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Triggers deterministic AST indexing and graph construction for a repository workspace."""
    workspace_path = req.workspace or "."
    repo_id = req.repository_id

    # If repo_id is provided, verify or find repository
    if repo_id:
        res = await db.execute(select(Repository).where(Repository.id == repo_id))
        repo = res.scalars().first()
        if not repo and repo_id != "local-workspace":
            # Allow fallback if using test or mock repo id
            pass

    resolved_workspace = Path(workspace_path).resolve()
    if not resolved_workspace.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace path '{workspace_path}' does not exist on disk.",
        )

    indexer = RepositoryIndexer(workspace_root=resolved_workspace)
    result = await indexer.index_repository(
        repository_id=repo_id or "local-workspace",
        force_full=req.force_full,
        session=db,
    )
    return result


# 2. Get Index Status
@router.get("/status/{repository_id}")
async def get_index_status(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves index status, last run time, and statistics for a repository."""
    # Query latest run
    run_res = await db.execute(
        select(CodeIndexRun)
        .where(CodeIndexRun.repository_id == repository_id)
        .order_by(desc(CodeIndexRun.created_at))
        .limit(1)
    )
    latest_run = run_res.scalars().first()

    # Query counts
    files_count = await db.scalar(
        select(func.count(CodeFile.id)).where(CodeFile.repository_id == repository_id)
    ) or 0
    symbols_count = await db.scalar(
        select(func.count(CodeSymbol.id)).where(CodeSymbol.repository_id == repository_id)
    ) or 0
    relationships_count = await db.scalar(
        select(func.count(CodeRelationship.id)).where(CodeRelationship.repository_id == repository_id)
    ) or 0

    return {
        "repository_id": repository_id,
        "status": latest_run.status if latest_run else IndexStatus.NOT_INDEXED.value,
        "last_indexed_at": latest_run.created_at.isoformat() if latest_run else None,
        "duration_ms": latest_run.duration_ms if latest_run else 0.0,
        "files_indexed": files_count,
        "symbols_indexed": symbols_count,
        "relationships_indexed": relationships_count,
        "error_message": latest_run.error_message if latest_run else None,
    }


# 3. List Indexed Files
@router.get("/files/{repository_id}")
async def list_indexed_files(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Lists all indexed files with language and metrics."""
    res = await db.execute(
        select(CodeFile)
        .where(CodeFile.repository_id == repository_id)
        .order_by(CodeFile.path)
    )
    files = res.scalars().all()
    return [
        {
            "id": f.id,
            "path": f.path,
            "language": f.language,
            "line_count": f.line_count,
            "size_bytes": f.size_bytes,
            "hash": f.hash,
            "indexed_at": f.indexed_at.isoformat(),
        }
        for f in files
    ]


# 4. List / Filter Symbols
@router.get("/symbols/{repository_id}")
async def list_symbols(
    repository_id: str,
    file_id: Optional[str] = None,
    kind: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Lists symbols for a repository with kind, file, and query filters."""
    stmt = (
        select(CodeSymbol, CodeFile.path)
        .join(CodeFile, CodeSymbol.file_id == CodeFile.id)
        .where(CodeSymbol.repository_id == repository_id)
    )

    if file_id:
        stmt = stmt.where(CodeSymbol.file_id == file_id)
    if kind:
        stmt = stmt.where(CodeSymbol.kind == kind.lower())
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                CodeSymbol.name.ilike(pattern),
                CodeSymbol.qualified_name.ilike(pattern),
            )
        )

    stmt = stmt.order_by(CodeSymbol.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": s.id,
            "file_id": s.file_id,
            "file_path": file_path,
            "name": s.name,
            "qualified_name": s.qualified_name,
            "kind": s.kind,
            "start_line": s.start_line,
            "end_line": s.end_line,
            "signature": s.signature,
            "docstring": s.docstring,
            "parent_symbol_id": s.parent_symbol_id,
        }
        for s, file_path in rows
    ]


# 5. Get Symbol Detail
@router.get("/symbols/{repository_id}/{symbol_id}")
async def get_symbol_detail(
    repository_id: str,
    symbol_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full details for a symbol including parent and callers/callees."""
    res = await db.execute(
        select(CodeSymbol, CodeFile.path)
        .join(CodeFile, CodeSymbol.file_id == CodeFile.id)
        .where(CodeSymbol.repository_id == repository_id, CodeSymbol.id == symbol_id)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol_id}' not found.")

    symbol, file_path = row

    # Inbound / Outbound relationships
    rel_in = await db.execute(
        select(CodeRelationship).where(
            CodeRelationship.repository_id == repository_id,
            CodeRelationship.target_id.like(f"%{symbol.qualified_name}%"),
        )
    )
    callers = [{"type": r.relationship_type, "source": r.source_id, "confidence": r.confidence} for r in rel_in.scalars().all()]

    rel_out = await db.execute(
        select(CodeRelationship).where(
            CodeRelationship.repository_id == repository_id,
            CodeRelationship.source_id.like(f"%{symbol.qualified_name}%"),
        )
    )
    callees = [{"type": r.relationship_type, "target": r.target_id, "confidence": r.confidence} for r in rel_out.scalars().all()]

    return {
        "id": symbol.id,
        "file_id": symbol.file_id,
        "file_path": file_path,
        "name": symbol.name,
        "qualified_name": symbol.qualified_name,
        "kind": symbol.kind,
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
        "signature": symbol.signature,
        "docstring": symbol.docstring,
        "parent_symbol_id": symbol.parent_symbol_id,
        "metadata": symbol.metadata_json,
        "callers": callers,
        "callees": callees,
    }


# 6. Multi-Tier Code Search
@router.post("/search", response_model=CodeSearchResponse)
async def search_code_endpoint(
    req: CodeSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Executes multi-tier code search (Tier 1 Ripgrep, Tier 2 Symbol, Tier 3 Path, Tier 4 Semantic)."""
    workspace = req.workspace or "."
    search_coord = MultiTierSearchCoordinator(workspace_root=workspace)

    response = await search_coord.execute_search(
        query=req.query,
        tier=req.tier,
        path_filter=req.path_filter,
        max_results=req.max_results,
        case_sensitive=req.case_sensitive,
        session=db,
        repository_id=req.repository_id,
    )
    return response


# 7. Get Repository Graph
@router.get("/graph/{repository_id}", response_model=RepositoryGraphData)
async def get_repository_graph(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetches the complete dependency and symbol graph for visualization and analysis."""
    # Query files
    files_res = await db.execute(select(CodeFile).where(CodeFile.repository_id == repository_id))
    files = files_res.scalars().all()

    # Query symbols
    symbols_res = await db.execute(select(CodeSymbol, CodeFile.path).join(CodeFile, CodeSymbol.file_id == CodeFile.id).where(CodeSymbol.repository_id == repository_id))
    symbols = symbols_res.all()

    # Query relationships
    rels_res = await db.execute(select(CodeRelationship).where(CodeRelationship.repository_id == repository_id))
    relationships = rels_res.scalars().all()

    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    for f in files:
        nodes.append(
            GraphNode(
                id=f"file:{f.path}",
                type="file",
                label=f.path,
                metadata={"language": f.language, "lines": f.line_count, "size": f.size_bytes},
            )
        )

    for s, file_path in symbols:
        nodes.append(
            GraphNode(
                id=f"symbol:{file_path}:{s.qualified_name}",
                type="symbol",
                label=s.name,
                metadata={"file": file_path, "kind": s.kind, "signature": s.signature},
            )
        )

    for r in relationships:
        edges.append(
            GraphEdge(
                id=r.id,
                source_id=r.source_id,
                target_id=r.target_id,
                type=r.relationship_type,
                confidence=r.confidence,
                resolution_status=r.resolution_status,
                metadata=r.metadata_json,
            )
        )

    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "files": len(files),
        "symbols": len(symbols),
        "relationships": len(relationships),
    }

    return RepositoryGraphData(
        repository_id=repository_id,
        nodes=nodes,
        edges=edges,
        stats=stats,
    )


# 8. Get Discovered Test Mappings
@router.get("/tests/{repository_id}")
async def get_test_mappings(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns discovered test-to-source mappings for the repository."""
    stmt = (
        select(
            CodeTestMapping,
            CodeFile.path.label("source_path"),
        )
        .join(CodeFile, CodeTestMapping.source_file_id == CodeFile.id)
        .where(CodeTestMapping.repository_id == repository_id)
    )
    res = await db.execute(stmt)
    rows = res.all()

    # Fetch test file paths
    results = []
    for tm, source_path in rows:
        test_file_res = await db.execute(select(CodeFile.path).where(CodeFile.id == tm.test_file_id))
        test_path = test_file_res.scalar() or "unknown"
        results.append({
            "id": tm.id,
            "test_file": test_path,
            "source_file": source_path,
            "relationship_type": tm.relationship_type,
            "confidence": tm.confidence,
            "created_at": tm.created_at.isoformat(),
        })

    return results


# 9. Git Intelligence Endpoints
@router.get("/git/history")
async def git_history_endpoint(
    workspace: str = ".",
    path: Optional[str] = None,
    limit: int = Query(15, ge=1, le=100),
):
    """Returns commit history with author attribution and messages."""
    git_intel = GitIntelligence(workspace_root=workspace)
    return git_intel.get_commit_history(path=path, limit=limit)


@router.get("/git/blame")
async def git_blame_endpoint(
    path: str,
    workspace: str = ".",
    start_line: int = Query(1, ge=1),
    end_line: int = Query(100, ge=1),
):
    """Returns git blame lines for a file."""
    git_intel = GitIntelligence(workspace_root=workspace)
    return git_intel.get_file_blame(path=path, start_line=start_line, end_line=end_line)


@router.get("/git/co-occurrence")
async def git_co_occurrence_endpoint(
    path: str,
    workspace: str = ".",
    limit_commits: int = Query(50, ge=5, le=200),
):
    """Returns files that frequently change together with target path."""
    git_intel = GitIntelligence(workspace_root=workspace)
    return git_intel.get_change_co_occurrence(path=path, limit_commits=limit_commits)
