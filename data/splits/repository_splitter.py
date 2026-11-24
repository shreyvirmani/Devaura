"""Devaura Real Data Pipeline: Repository-Level Splitter.

Enforces zero repository leakage across Train, Validation, and Held-Out Test splits.
Bugs from the same repository are guaranteed to reside in exactly one split partition.
"""

from typing import Dict, List, Optional, Set, Tuple
from data.normalization.normalizer import BugFixRecord


class RepositoryLeakageError(ValueError):
    """Raised when bugs from the same repository are placed in multiple splits."""
    pass


class RepositorySplitter:
    """Partitions defect records across train, validation, and test at the repository boundary."""

    # Canonical default partition of prominent open-source ecosystems
    DEFAULT_REPOSITORY_ASSIGNMENTS: Dict[str, str] = {
        # Train repositories
        "pallets/flask": "train",
        "psf/requests": "train",
        "pallets/click": "train",
        "tornadoweb/tornado": "train",
        "marshmallow-code/marshmallow": "train",
        "encode/httpx": "train",
        # Validation repositories
        "tiangolo/fastapi": "validation",
        "sqlalchemy/sqlalchemy": "validation",
        "expressjs/express": "validation",
        # Test repositories (Strictly held-out, never evaluated during prompt tuning)
        "pydantic/pydantic": "test",
        "pytest-dev/pytest": "test",
        "urllib3/urllib3": "test",
        "chalk/chalk": "test",
        "axios/axios": "test",
        "lodash/lodash": "test",
        "gin-gonic/gin": "test",
        "pallets/jinja": "test",
        "Textualize/rich": "test",
        "serde-rs/serde": "test",
        "google/guava": "test",
        "mitmproxy/mitmproxy": "test",
        "boto/botocore": "test",
    }

    @classmethod
    def assign_splits(
        cls,
        records: List[BugFixRecord],
        repo_assignments: Optional[Dict[str, str]] = None,
    ) -> Dict[str, List[BugFixRecord]]:
        """Assign records to train, validation, and test splits based on repository boundary."""
        assignments = repo_assignments or cls.DEFAULT_REPOSITORY_ASSIGNMENTS
        splits: Dict[str, List[BugFixRecord]] = {"train": [], "validation": [], "test": []}
        seen_repo_splits: Dict[str, str] = {}

        for rec in records:
            repo = rec.repository
            target_split = assignments.get(repo, "train")

            # Verify no cross-split leakage for this repository
            if repo in seen_repo_splits and seen_repo_splits[repo] != target_split:
                raise RepositoryLeakageError(
                    f"Repository leakage detected: '{repo}' is assigned to both "
                    f"'{seen_repo_splits[repo]}' and '{target_split}'!"
                )
            seen_repo_splits[repo] = target_split

            rec.dataset_split = target_split
            splits[target_split].append(rec)

        return splits

    @classmethod
    def verify_no_repo_overlap(cls, splits: Dict[str, List[BugFixRecord]]) -> None:
        """Mathematically verifies disjoint repository sets across train, val, and test."""
        train_repos = {r.repository for r in splits.get("train", [])}
        val_repos = {r.repository for r in splits.get("validation", [])}
        test_repos = {r.repository for r in splits.get("test", [])}

        overlap_tv = train_repos.intersection(val_repos)
        overlap_tt = train_repos.intersection(test_repos)
        overlap_vt = val_repos.intersection(test_repos)

        if overlap_tv:
            raise RepositoryLeakageError(f"Overlap between Train and Validation repos: {overlap_tv}")
        if overlap_tt:
            raise RepositoryLeakageError(f"Overlap between Train and Test repos: {overlap_tt}")
        if overlap_vt:
            raise RepositoryLeakageError(f"Overlap between Validation and Test repos: {overlap_vt}")
