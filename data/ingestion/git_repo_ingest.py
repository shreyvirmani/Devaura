"""Devaura Real Data Pipeline: Git Repository Workspace Ingestion.

Clones or operates on local git repositories in isolated workspaces to checkout
buggy revisions, extract failing test cases, generate golden unified diffs,
and verify fix reproducibility without polluting runtime environments.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from data.validation.secret_detector import SecretDetector


class GitIngestionError(Exception):
    """Raised when git checkout or diff operations fail."""
    pass


class GitRepositoryIngest:
    """Manages isolated git workspace checkouts and commit inspection."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or tempfile.gettempdir()) / "devaura_data_ingest"
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def checkout_revision(self, repo_path: str, revision: str) -> None:
        """Checkout a specific git commit or tag in the specified repo."""
        cmd = ["git", "checkout", "-f", revision]
        res = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        if res.returncode != 0:
            raise GitIngestionError(f"Failed to checkout {revision} in {repo_path}: {res.stderr}")

    def get_diff_between_revisions(self, repo_path: str, base_sha: str, target_sha: str) -> str:
        """Generate unified diff between buggy and fixing revisions."""
        cmd = ["git", "diff", f"{base_sha}..{target_sha}"]
        res = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        if res.returncode != 0:
            raise GitIngestionError(f"Failed to diff {base_sha}..{target_sha}: {res.stderr}")
        return SecretDetector.sanitize(res.stdout)

    def extract_file_content_at_revision(self, repo_path: str, revision: str, file_path: str) -> str:
        """Extract the exact content of a file at a specific revision via git show."""
        cmd = ["git", "show", f"{revision}:{file_path}"]
        res = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        if res.returncode != 0:
            raise GitIngestionError(f"Failed to get {file_path} at {revision}: {res.stderr}")
        return SecretDetector.sanitize(res.stdout)
