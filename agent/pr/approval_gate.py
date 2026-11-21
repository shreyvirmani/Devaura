"""Devaura Phase 7 Human PR Approval Gate.

Cryptographically binds human authorization to the exact repair ID, patch hash,
base revision, repair branch, repository identity, and PR operation.
Prevents automated agent self-approvals and detects post-approval tampering.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import os
import uuid
from typing import Optional

from agent.pr.models import PRApproval, PRApprovalStatus


class PRApprovalRequiredError(PermissionError):
    """Raised when an automated agent or unauthenticated entity attempts PR creation."""
    pass


class PRPatchIntegrityError(ValueError):
    """Raised when a patch or git parameter changes after PR authorization."""
    pass


class HumanPRApprovalGate:
    """Cryptographic authorization gate specifically guarding GitHub Pull Request creation."""

    _SECRET_KEY = os.getenv("DEVAURA_SECRET_KEY", "devaura-pr-authorization-secret-key-32b").encode("utf-8")

    def __init__(self, secret_key: Optional[str] = None):
        self._secret = secret_key.encode("utf-8") if secret_key else self._SECRET_KEY

    def _get_key(self) -> bytes:
        return getattr(self, "_secret", self._SECRET_KEY)

    def generate_approval_token(
        self,
        repair_id: str,
        patch_hash: str,
        base_revision: str,
        repair_branch: str,
        repository: str,
        operation: str = "CREATE_PULL_REQUEST",
    ) -> str:
        """Generate deterministic HMAC-SHA256 signature binding all critical PR parameters."""
        key = self._get_key()
        message = f"{repair_id}:{patch_hash}:{base_revision}:{repair_branch}:{repository}:{operation}".encode("utf-8")
        signature = hmac.new(key, message, hashlib.sha256).hexdigest()
        return f"pr-auth-{signature[:32]}-{uuid.uuid4().hex[:8]}"

    def create_approval(
        self,
        repair_id: str,
        patch_hash: str,
        base_revision: str,
        repair_branch: str,
        repository: str,
        user_identity: str,
        operation: str = "CREATE_PULL_REQUEST",
    ) -> PRApproval:
        """Create a valid human PR approval record."""
        # 1. Guard against autonomous agent self-approval
        sanitized_user = (user_identity or "").strip().lower()
        user_prefix = sanitized_user.split("@")[0].strip()
        forbidden_terms = {"agent", "bot", "devaura-agent", "devaura-bot", "system", "autonomous", "autonomous-loop", "loop"}
        if not sanitized_user or user_prefix in forbidden_terms or "agent" in user_prefix or "bot" in user_prefix:
            raise PRApprovalRequiredError(
                f"Autonomous agent self-approval is forbidden ('{user_identity}'). Explicit human approval is mandatory."
            )

        token = self.generate_approval_token(
            repair_id=repair_id,
            patch_hash=patch_hash,
            base_revision=base_revision,
            repair_branch=repair_branch,
            repository=repository,
            operation=operation,
        )

        return PRApproval(
            repair_id=repair_id,
            patch_hash=patch_hash,
            base_revision=base_revision,
            repair_branch=repair_branch,
            repository=repository,
            operation=operation,
            approved_by=user_identity,
            approved_at=datetime.now(timezone.utc),
            approval_token=token,
            status=PRApprovalStatus.APPROVED,
        )

    def verify_authorization(
        self,
        approval: PRApproval,
        current_patch_hash: str,
        current_base_revision: str,
        current_repair_branch: str,
        current_repository: str,
        operation: str = "CREATE_PULL_REQUEST",
    ) -> bool:
        """Verify that PR authorization token remains cryptographically valid and untampered."""
        if approval.status != PRApprovalStatus.APPROVED:
            raise PRApprovalRequiredError(
                f"Cannot proceed with PR: Authorization status is '{approval.status}'."
            )

        if not approval.approval_token or not approval.approval_token.startswith("pr-auth-"):
            raise PRApprovalRequiredError("Invalid or missing PR authorization token format.")

        # Guard: Patch hash integrity
        if approval.patch_hash != current_patch_hash:
            raise PRPatchIntegrityError(
                f"PR Authorization invalidated: Patch hash '{current_patch_hash[:8]}' does not match approved hash '{approval.patch_hash[:8]}'."
            )

        # Guard: Base revision integrity
        if approval.base_revision != current_base_revision:
            raise PRPatchIntegrityError(
                f"PR Authorization invalidated: Base revision '{current_base_revision[:8]}' does not match approved base '{approval.base_revision[:8]}'."
            )

        # Guard: Repair branch integrity
        if approval.repair_branch != current_repair_branch:
            raise PRPatchIntegrityError(
                f"PR Authorization invalidated: Branch '{current_repair_branch}' does not match approved branch '{approval.repair_branch}'."
            )

        # Guard: Repository integrity
        if approval.repository != current_repository:
            raise PRPatchIntegrityError(
                f"PR Authorization invalidated: Repository '{current_repository}' does not match approved repo '{approval.repository}'."
            )

        # Guard: Operation integrity
        if approval.operation != operation:
            raise PRPatchIntegrityError(
                f"PR Authorization invalidated: Operation '{operation}' does not match approved operation '{approval.operation}'."
            )

        # Verify HMAC signature segment
        expected_prefix = self.generate_approval_token(
            repair_id=approval.repair_id,
            patch_hash=current_patch_hash,
            base_revision=current_base_revision,
            repair_branch=current_repair_branch,
            repository=current_repository,
            operation=operation,
        )[:40]  # "pr-auth-" + 32 hex chars

        if not approval.approval_token.startswith(expected_prefix):
            raise PRPatchIntegrityError("PR Authorization token cryptographic signature mismatch.")

        return True
