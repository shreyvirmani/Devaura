"""Devaura Human Approval Gate.

Enforces strict human-in-the-loop governance:
1. No automated self-approval by the agent.
2. Cryptographic binding between human authorization and SHA-256(unified_diff).
3. Re-validation prior to patch application to detect post-approval mutations.
"""

import hashlib
import uuid
from typing import Optional

from agent.repair.models import ApprovalStatus, RepairApproval


class ApprovalRequiredError(PermissionError):
    """Raised when an unapproved patch application is attempted."""
    pass


class PatchIntegrityError(ValueError):
    """Raised when a patch diff does not match its approved SHA-256 hash."""
    pass


class HumanApprovalGate:
    """Manages cryptographic human approvals for repair patches."""

    def __init__(self):
        pass

    @classmethod
    def compute_patch_hash(cls, unified_diff: str) -> str:
        """Calculate deterministic SHA-256 digest of unified diff."""
        return hashlib.sha256(unified_diff.strip().encode("utf-8")).hexdigest()

    def create_approval(
        self,
        repair_id: str,
        unified_diff: str,
        user_identity: str,
    ) -> RepairApproval:
        """Issue human approval cryptographically bound to exact patch content."""
        if not user_identity or user_identity.lower() in {"agent", "bot", "system", "auto"}:
            raise ApprovalRequiredError(
                f"Agent self-approval is forbidden. Approval requires human identity, got: '{user_identity}'"
            )

        patch_hash = self.compute_patch_hash(unified_diff)
        token = str(uuid.uuid4())

        return RepairApproval(
            repair_id=repair_id,
            patch_hash=patch_hash,
            approved_by=user_identity,
            status=ApprovalStatus.APPROVED,
            approval_token=token,
        )

    def reject_repair(
        self,
        repair_id: str,
        unified_diff: str,
        user_identity: str,
        reason: Optional[str] = None,
    ) -> RepairApproval:
        """Record human rejection of proposed repair."""
        patch_hash = self.compute_patch_hash(unified_diff)
        token = str(uuid.uuid4())

        return RepairApproval(
            repair_id=repair_id,
            patch_hash=patch_hash,
            approved_by=user_identity,
            status=ApprovalStatus.REJECTED,
            approval_token=token,
            rejection_reason=reason or "Rejected by human reviewer.",
        )

    def verify_authorization(
        self,
        approval: RepairApproval,
        current_unified_diff: str,
    ) -> bool:
        """Verify that current diff exactly matches approved cryptographic hash."""
        if approval.status != ApprovalStatus.APPROVED:
            raise ApprovalRequiredError(
                f"Cannot apply patch: approval status is '{approval.status.value}'"
            )

        current_hash = self.compute_patch_hash(current_unified_diff)
        if approval.patch_hash != current_hash:
            raise PatchIntegrityError(
                f"Cryptographic hash mismatch! Approved hash '{approval.patch_hash}' "
                f"does not match current patch hash '{current_hash}'. Patch has been altered."
            )

        return True
