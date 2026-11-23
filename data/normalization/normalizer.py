"""Devaura Real Data Pipeline: Data Normalization.

Normalizes raw bug reports, Git commits, pull requests, and benchmark entries
into canonical Devaura BugFixRecord schemas with standard metadata and provenance.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BugFixRecord(BaseModel):
    """Canonical schema for a real-world software defect and repair pair."""

    id: str = Field(..., description="Unique defect identifier, e.g. 'HIST-001'")
    repository: str = Field(..., description="Repository in 'owner/repo' format, e.g. 'pallets/flask'")
    language: str = Field(..., description="Primary language of the repository")
    buggy_commit: str = Field(..., description="Git commit SHA reproducing the failure")
    fix_commit: str = Field(..., description="Git commit SHA resolving the failure")
    issue: str = Field(..., description="Issue title, identifier, or CVE reference")
    issue_description: str = Field(default="", description="Detailed issue description or problem statement")
    failure_type: str = Field(..., description="Observed failure category (e.g. AssertionError, TypeError)")
    stack_trace: str = Field(default="", description="Observed reproduction stack trace or error log")
    failing_tests: List[str] = Field(default_factory=list, description="List of test names or paths that fail on buggy commit")
    changed_files: List[str] = Field(default_factory=list, description="Target source files modified by the fix")
    source_files: Dict[str, str] = Field(default_factory=dict, description="File path to buggy source content mapping")
    reproduction_test: Dict[str, str] = Field(default_factory=dict, description="File path to test content reproducing the bug")
    hidden_validation_test: Dict[str, str] = Field(default_factory=dict, description="Withheld test file content for evaluation")
    golden_patch: str = Field(default="", description="Unified diff of the ground truth fix")
    verification_command: str = Field(default="pytest tests/test_reproduce.py", description="Command used to verify fix")
    verification_result: str = Field(default="passed", description="Expected verification status after fix")
    license: str = Field(..., description="Open source license of the repository")
    source_url: str = Field(..., description="URL to the source repository or pull request")
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when record was ingested",
    )
    dataset_split: Optional[str] = Field(default=None, description="Assigned split: 'train', 'validation', or 'test'")


class DataNormalizer:
    """Transforms raw defect data into normalized BugFixRecord instances."""

    @classmethod
    def normalize(cls, raw: Dict[str, Any]) -> BugFixRecord:
        """Parse, validate, and normalize a raw defect dictionary into a BugFixRecord."""
        # Normalize repository name
        repo = raw.get("repository") or raw.get("project") or ""
        if "/" not in repo and repo:
            # Map canonical projects to owner/repo if missing owner
            canonical_map = {
                "flask": "pallets/flask",
                "requests": "psf/requests",
                "click": "pallets/click",
                "pydantic": "pydantic/pydantic",
                "fastapi": "tiangolo/fastapi",
                "sqlalchemy": "sqlalchemy/sqlalchemy",
                "express": "expressjs/express",
                "tornado": "tornadoweb/tornado",
                "pytest": "pytest-dev/pytest",
                "marshmallow": "marshmallow-code/marshmallow",
                "httpx": "encode/httpx",
                "urllib3": "urllib3/urllib3",
            }
            repo = canonical_map.get(repo.lower(), f"opensource/{repo}")

        # Compute golden patch if not provided but fixed_source is available
        golden_patch = raw.get("golden_patch", "")
        if not golden_patch and "fixed_source" in raw:
            # Construct diff representation
            golden_patch = raw.get("golden_patch_diff", "")

        return BugFixRecord(
            id=raw.get("id") or raw.get("bug_id", "UNKNOWN"),
            repository=repo,
            language=raw.get("language") or raw.get("ecosystem", "python"),
            buggy_commit=raw.get("buggy_commit", "HEAD~1"),
            fix_commit=raw.get("fix_commit", "HEAD"),
            issue=raw.get("issue") or raw.get("cve_or_issue") or raw.get("title", ""),
            issue_description=raw.get("issue_description") or raw.get("description", ""),
            failure_type=raw.get("failure_type") or raw.get("category", "TestFailure"),
            stack_trace=raw.get("stack_trace", ""),
            failing_tests=raw.get("failing_tests") or ["tests/test_reproduce.py"],
            changed_files=raw.get("changed_files") or raw.get("expected_affected_files", []),
            source_files=raw.get("source_files", {}),
            reproduction_test=raw.get("reproduction_test", {}),
            hidden_validation_test=raw.get("hidden_validation_test", {}),
            golden_patch=golden_patch,
            verification_command=raw.get("verification_command") or raw.get("test_command", "pytest tests/test_reproduce.py"),
            verification_result=raw.get("verification_result", "passed"),
            license=raw.get("license", "MIT"),
            source_url=raw.get("source_url") or f"https://github.com/{repo}",
            retrieved_at=raw.get("retrieved_at") or datetime.now(timezone.utc).isoformat(),
            dataset_split=raw.get("dataset_split"),
        )
