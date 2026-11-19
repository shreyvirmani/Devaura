from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SymbolKindEnum(str, Enum):
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    MODULE = "module"


class RelationshipKindEnum(str, Enum):
    CONTAINS = "CONTAINS"
    DEFINES = "DEFINES"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    EXTENDS = "EXTENDS"
    TESTS = "TESTS"


class ResolutionStatusEnum(str, Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


class TestEvidenceKind(str, Enum):
    IMPORT = "IMPORT"
    DIRECT_CALL = "DIRECT_CALL"
    SYMBOL_REFERENCE = "SYMBOL_REFERENCE"
    NAME_MATCH = "NAME_MATCH"
    PATH_MATCH = "PATH_MATCH"
    HEURISTIC = "HEURISTIC"


@dataclass
class ParsedCall:
    name: str
    line_number: int = 1
    callee_expr: str = ""

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.name == other or self.callee_expr == other
        if isinstance(other, ParsedCall):
            return self.name == other.name and self.line_number == other.line_number
        return False

    def __str__(self) -> str:
        return self.name


@dataclass
class ParsedSymbol:
    name: str
    qualified_name: str
    kind: SymbolKindEnum
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_name: Optional[str] = None
    calls: List[ParsedCall] = field(default_factory=list)
    extends: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedImport:
    module: str
    symbol_name: Optional[str] = None
    alias: Optional[str] = None
    is_external: bool = False
    line_number: int = 1


@dataclass
class ParsedFile:
    path: str
    language: str
    hash: str
    size_bytes: int
    line_count: int
    symbols: List[ParsedSymbol] = field(default_factory=list)
    imports: List[ParsedImport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# Pydantic Schemas for API and MCP Tools

class CodeSearchRequest(BaseModel):
    query: str = Field(..., description="Search query string or regex pattern")
    repository_id: Optional[str] = Field(None, description="Repository identifier")
    workspace: Optional[str] = Field(None, description="Workspace directory path")
    tier: str = Field("all", description="Search tier: 'ripgrep', 'symbol', 'path', or 'all'")
    path_filter: Optional[str] = Field(None, description="Optional path substring or glob filter")
    max_results: int = Field(25, ge=1, le=100, description="Maximum results to return")
    case_sensitive: bool = Field(False, description="Case-sensitive search")


class SearchMatch(BaseModel):
    tier: str = Field(..., description="ripgrep, symbol, or path")
    file: str
    line: int = 1
    column: int = 1
    text: str = ""
    symbol_name: Optional[str] = None
    kind: Optional[str] = None
    score: float = 1.0


class CodeSearchResponse(BaseModel):
    query: str
    total_matches: int
    matches: List[SearchMatch]


class IndexRepositoryRequest(BaseModel):
    repository_id: Optional[str] = None
    workspace: str = "."
    force_full: bool = False


class IndexRepositoryResponse(BaseModel):
    repository_id: str
    status: str
    files_indexed: int
    symbols_indexed: int
    duration_ms: float
    error_message: Optional[str] = None


class GraphNode(BaseModel):
    id: str
    type: str  # "file" or "symbol"
    label: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    type: str  # CONTAINS, DEFINES, IMPORTS, CALLS, EXTENDS, TESTS
    confidence: float = 1.0
    resolution_status: str = "RESOLVED"
    evidence: str = ""
    source_location: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RepositoryGraphData(BaseModel):
    repository_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: Dict[str, int] = Field(default_factory=dict)
