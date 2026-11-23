"""Devaura Real Data Pipeline: Provenance Tracking.

Captures and enforces auditable provenance metadata for all ingested software artifacts:
repository, commit SHAs, issue IDs, PR numbers, file paths, authors, licenses, and timestamps.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
    """Complete provenance envelope for an ingested artifact or defect record."""

    source_provider: str = Field(..., description="Provider source, e.g. 'github', 'git-local', 'cve-database'")
    repository: str = Field(..., description="Full repository identifier, e.g. 'pallets/flask'")
    source_url: str = Field(..., description="Canonical public URL for the source repository")
    commit_sha: Optional[str] = Field(None, description="Buggy commit SHA")
    fix_commit_sha: Optional[str] = Field(None, description="Ground truth fixing commit SHA")
    issue_number: Optional[int] = Field(None, description="Public issue number")
    pr_number: Optional[int] = Field(None, description="Public pull request number")
    file_paths: List[str] = Field(default_factory=list, description="Target affected source file paths")
    author: Optional[str] = Field(None, description="Author or reporter handle")
    license: str = Field(..., description="Permissive license name, e.g. 'BSD-3-Clause', 'Apache-2.0', 'MIT'")
    language: str = Field(..., description="Primary programming language, e.g. 'python', 'javascript'")
    bug_category: str = Field(..., description="Categorization of defect, e.g. 'Routing / URL Parsing'")
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of when the record was ingested",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provider-specific metadata")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProvenanceTracker:
    """Manages recording and verification of artifact provenance."""

    def __init__(self):
        self._records: Dict[str, ProvenanceRecord] = {}

    def register_record(self, record_id: str, record: ProvenanceRecord) -> None:
        """Register a new provenance record."""
        self._records[record_id] = record

    def get_record(self, record_id: str) -> Optional[ProvenanceRecord]:
        """Retrieve a provenance record by ID."""
        return self._records.get(record_id)

    def validate_provenance(self, record: ProvenanceRecord) -> bool:
        """Ensures non-empty source provider, repository, license, and valid URL."""
        if not record.source_provider or not record.repository or not record.source_url:
            return False
        if not record.license or record.license.upper() in {"PROPRIETARY", "UNKNOWN"}:
            return False
        return True
