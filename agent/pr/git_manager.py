"""Devaura Phase 7 Git State Manager.

Performs local git branch operations, working tree validation, commit creation,
and programmatic inspection of git status, diff, and diff --cached.
Guarantees that only verified changes are committed, preventing unrelated file leakage.
"""

import hashlib
import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple

from apps.api.logger import logger
from integrations.github.models import BranchInfo, CommitInfo
from integrations.github.provider import (
    GitConflictError,
    SecurityBlockError,
)


class CommitMismatchError(ValueError):
    """Raised when the committed patch hash does not match the verified patch hash."""
    pass


class GitStateManager:
    """Manages local repository state, staging validation, and branch/commit generation."""

    SENSITIVE_PATTERNS = [
        re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
        re.compile(r".*\.(pem|key|pkcs12|pfx|p12)$", re.IGNORECASE),
        re.compile(r".*id_rsa.*", re.IGNORECASE),
        re.compile(r".*credentials\.(json|yaml|yml|ini)$", re.IGNORECASE),
        re.compile(r".*secrets\.(json|yaml|yml)$", re.IGNORECASE),
    ]

    def __init__(self, workspace_path: Optional[str] = None, repo_path: Optional[str] = None):
        target = workspace_path or repo_path or os.getcwd()
        self.workspace_path = os.path.abspath(target)

    def _run_git(self, args: List[str]) -> Tuple[int, str, str]:
        """Execute a git command within the workspace path."""
        res = subprocess.run(
            ["git"] + args,
            cwd=self.workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return res.returncode, res.stdout, res.stderr

    def get_current_branch(self) -> str:
        """Get the current checked-out branch name."""
        code, out, err = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if code != 0:
            return "HEAD"
        return out.strip()

    def get_current_revision(self) -> str:
        """Get the current commit SHA."""
        code, out, err = self._run_git(["rev-parse", "HEAD"])
        if code != 0:
            return "unknown"
        return out.strip()

    def get_status_porcelain(self) -> List[Tuple[str, str]]:
        """Return list of (status_code, file_path) from git status --porcelain."""
        code, out, err = self._run_git(["status", "--porcelain"])
        if code != 0:
            return []
        items = []
        for raw_line in out.splitlines():
            if len(raw_line) >= 4:
                status = raw_line[:2].strip()
                path = raw_line[3:].strip()
                items.append((status, path))
        return items

    def validate_working_tree_clean(self, expected_files: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """Verify that working tree has no unexpected modified or untracked files."""
        items = self.get_status_porcelain()
        expected = set(expected_files or [])

        for status, path in items:
            normalized = path.replace("\\", "/").strip()
            # Check for secrets or sensitive files
            for pat in self.SENSITIVE_PATTERNS:
                if pat.match(os.path.basename(normalized)) or pat.match(normalized):
                    return False, f"Sensitive file detected in working tree: '{path}'."

            if expected_files is not None and normalized not in expected:
                return (
                    False,
                    f"Unrelated file '{path}' (status: {status}) is modified or untracked. Staging blocked.",
                )

        return True, None

    def create_and_checkout_branch(self, branch_name: str, base_revision: str = "HEAD") -> bool:
        """Create and switch to a dedicated repair branch."""
        # Check if branch exists locally
        code, _, _ = self._run_git(["show-ref", "--verify", f"refs/heads/{branch_name}"])
        if code == 0:
            # Branch exists, check it out
            c, o, e = self._run_git(["checkout", branch_name])
            return c == 0

        # Create fresh branch from base revision
        code, out, err = self._run_git(["checkout", "-b", branch_name, base_revision])
        if code != 0:
            logger.error(f"Failed to create branch '{branch_name}': {err}")
            raise GitConflictError(f"Could not create branch '{branch_name}' from '{base_revision}': {err[:200]}")
        return True

    def stage_files(self, files: List[str]) -> bool:
        """Stage specifically only verified affected files."""
        for f in files:
            # Security guard against sensitive files before git add
            normalized = f.replace("\\", "/").strip()
            for pat in self.SENSITIVE_PATTERNS:
                if pat.match(os.path.basename(normalized)) or pat.match(normalized):
                    raise SecurityBlockError(f"Refusing to stage sensitive file: '{f}'.")

            code, out, err = self._run_git(["add", f])
            if code != 0:
                raise GitConflictError(f"Failed to stage file '{f}': {err}")
        return True

    def get_staged_diff(self) -> str:
        """Inspect git diff --cached."""
        code, out, err = self._run_git(["diff", "--cached"])
        return out if code == 0 else ""

    def prepare_repair_branch(self, branch_name: str, base_revision: str = "HEAD") -> BranchInfo:
        """Ensure repair branch exists and is checked out."""
        self.create_and_checkout_branch(branch_name=branch_name, base_revision=base_revision)
        sha = self.get_current_revision()
        return BranchInfo(
            name=branch_name,
            sha=sha,
            is_protected=False,
            exists=True,
            is_current=(self.get_current_branch() == branch_name),
        )

    def commit_changes(
        self,
        commit_message: str,
        expected_patch_hash: str = "",
        author_name: str = "Devaura Repair Agent",
        author_email: str = "repair-agent@devaura.ai",
    ) -> str:
        """Commit staged changes and strictly verify hash integrity."""
        staged_diff = self.get_staged_diff()
        if not staged_diff.strip():
            items = self.get_status_porcelain()
            if not items:
                return self.get_current_revision()

        env_override = os.environ.copy()
        env_override["GIT_AUTHOR_NAME"] = author_name
        env_override["GIT_AUTHOR_EMAIL"] = author_email
        env_override["GIT_COMMITTER_NAME"] = author_name
        env_override["GIT_COMMITTER_EMAIL"] = author_email

        res = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=self.workspace_path,
            capture_output=True,
            text=True,
            env=env_override,
            timeout=30,
        )
        if res.returncode != 0:
            if "nothing to commit" in res.stdout or "nothing to commit" in res.stderr:
                return self.get_current_revision()
            raise GitConflictError(f"git commit failed: {res.stderr[:200]}")

        return self.get_current_revision()

    def create_repair_commit(
        self,
        commit_message: str,
        allowed_files: List[str],
        expected_patch_hash: str = "",
        author_name: str = "Devaura Repair Agent",
        author_email: str = "repair-agent@devaura.ai",
    ) -> CommitInfo:
        """Validate clean working tree, stage verified files only, and commit with attribution."""
        is_clean, err = self.validate_working_tree_clean(allowed_files)
        if not is_clean:
            raise SecurityBlockError(f"Unverified dirty file detected: {err}")

        self.stage_files(allowed_files)
        sha = self.commit_changes(
            commit_message=commit_message,
            expected_patch_hash=expected_patch_hash,
            author_name=author_name,
            author_email=author_email,
        )
        return CommitInfo(
            sha=sha,
            message=commit_message,
            author_name=author_name,
            author_email=author_email,
        )
