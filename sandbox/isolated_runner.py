"""Devaura Isolated Sandbox Runner.

Executes patch application inside the isolated sandbox workspace and returns
the formal Phase 6 handoff contract: RepairExecutionResult.
"""

import os
from typing import Optional

from agent.repair.models import PatchResult, RepairExecutionResult
from apps.api.logger import logger
from sandbox.workspace import IsolatedWorkspace, PatchApplicationError


class IsolatedRunner:
    """Orchestrates patch application in an isolated sandbox workspace."""

    def __init__(self, workspace_base: Optional[str] = None):
        self.workspace_base = workspace_base

    def run_patch_application(
        self,
        repair_id: str,
        investigation_id: str,
        repository_id: str,
        source_repo_path: str,
        patch: PatchResult,
        base_revision: str = "HEAD",
    ) -> RepairExecutionResult:
        """Create sandbox, apply patch, and prepare verification handoff package."""
        workspace = IsolatedWorkspace(
            source_repo_path=source_repo_path,
            workspace_id=repair_id,
            base_dir=self.workspace_base,
        )

        # 1. Create isolated environment
        isolated_path = workspace.create()

        # 2. Apply patch
        try:
            modified_files = workspace.apply_patch(patch.unified_diff)
        except Exception as e:
            logger.error(f"Failed to apply patch in sandbox {isolated_path}: {e}")
            raise PatchApplicationError(f"Patch application failed in isolated sandbox: {e}")

        # 3. Construct resulting diff from sandbox
        applied_diff_chunks = []
        for mf in modified_files:
            diff_chunk = workspace.get_applied_diff(mf)
            if diff_chunk:
                applied_diff_chunks.append(diff_chunk)

        resulting_diff = "".join(applied_diff_chunks) or patch.unified_diff

        return RepairExecutionResult(
            repair_id=repair_id,
            investigation_id=investigation_id,
            repository=repository_id,
            base_revision=base_revision,
            workspace_id=workspace.workspace_id,
            isolated_path=isolated_path,
            patch_hash=patch.patch_hash,
            changed_files=modified_files,
            diff=resulting_diff,
            application_status="APPLIED",
            verification_status="PENDING",
        )
