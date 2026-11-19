import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.connection import Base
from database.models.models import Repository


def utc_now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


class SymbolKind(str, Enum):
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    MODULE = "module"


class RelationshipType(str, Enum):
    CONTAINS = "CONTAINS"
    DEFINES = "DEFINES"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    EXTENDS = "EXTENDS"
    TESTS = "TESTS"


class IndexStatus(str, Enum):
    NOT_INDEXED = "NOT_INDEXED"
    INDEXING = "INDEXING"
    READY = "READY"
    STALE = "STALE"
    FAILED = "FAILED"


# 1. Code File Model
class CodeFile(Base):
    __tablename__ = "code_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hash
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repository: Mapped["Repository"] = relationship("Repository", foreign_keys=[repository_id], lazy="selectin")
    symbols: Mapped[List["CodeSymbol"]] = relationship("CodeSymbol", back_populates="file", cascade="all, delete-orphan", lazy="selectin")
    imports: Mapped[List["CodeImport"]] = relationship("CodeImport", back_populates="file", cascade="all, delete-orphan", lazy="selectin")


# 2. Code Symbol Model
class CodeSymbol(Base):
    __tablename__ = "code_symbols"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_files.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    qualified_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), default=SymbolKind.FUNCTION.value, nullable=False, index=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    docstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_symbol_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("code_symbols.id", ondelete="CASCADE"), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    file: Mapped["CodeFile"] = relationship("CodeFile", back_populates="symbols")
    parent_symbol: Mapped[Optional["CodeSymbol"]] = relationship("CodeSymbol", remote_side=[id], lazy="selectin")


# 3. Code Relationship Model
class CodeRelationship(Base):
    __tablename__ = "code_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "file", "symbol"
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "file", "symbol", "module"
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # CONTAINS, DEFINES, IMPORTS, CALLS, EXTENDS, TESTS
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(50), default="RESOLVED", nullable=False)  # RESOLVED, PARTIAL, UNRESOLVED
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


# 4. Code Import Model
class CodeImport(Base):
    __tablename__ = "code_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_files.id", ondelete="CASCADE"), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    symbol_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    file: Mapped["CodeFile"] = relationship("CodeFile", back_populates="imports")


# 5. Code Index Run Model
class CodeIndexRun(Base):
    __tablename__ = "code_index_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default=IndexStatus.READY.value, nullable=False)
    files_indexed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    symbols_indexed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


# 6. Code Test Mapping Model
class CodeTestMapping(Base):
    __tablename__ = "code_test_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_files.id", ondelete="CASCADE"), nullable=False, index=True)
    test_file_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_files.id", ondelete="CASCADE"), nullable=False, index=True)
    source_symbol_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True, index=True)
    test_symbol_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), default="TESTS_FILE", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
