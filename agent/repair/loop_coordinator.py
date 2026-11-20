"""Devaura Bounded Repair Loop Coordinator.

Orchestrates the bounded retry lifecycle (up to 3 total attempts), ensuring
that follow-up attempts require distinct patches, full risk analysis, and
mandatory fresh human approvals.
"""

from typing import Dict, List, Optional, Tuple

from agent.repair.approval_gate import HumanApprovalGate
from agent.repair.models import (
    FailureAnalysisReport,
    PatchResult,
    PatchRisk,
    ProposedChange,
    RepairContext,
    RepairPlan,
    RepairState,
)
from agent.repair.patch_generator import PatchGenerator, ScopeViolationError
from agent.repair.planner import RepairPlanner
from agent.repair.risk_analyzer import PatchRiskAnalyzer
from agent.repair.state_machine import RepairStateMachine


class LoopLimitExceededError(ValueError):
    """Raised when an attempt beyond the 3-attempt limit is attempted."""
    pass


class NoProgressError(ValueError):
    """Raised when a retry patch is identical to previous patch with no progress."""
    pass


class RepairLoopCoordinator:
    """Enforces bounded repair loop rules and generates follow-up patch attempts."""

    MAX_ATTEMPTS = 3

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.planner = RepairPlanner()
        self.patch_generator = PatchGenerator(workspace_root=workspace_root)
        self.risk_analyzer = PatchRiskAnalyzer()

    def can_initiate_retry(
        self,
        current_attempt: int,
        failure_report: FailureAnalysisReport,
    ) -> Tuple[bool, Optional[str]]:
        """Validate whether a repair retry is legally permissible."""
        if current_attempt >= self.MAX_ATTEMPTS:
            return False, f"Maximum 3 total repair attempts exhausted ({current_attempt}/{self.MAX_ATTEMPTS})."

        if not failure_report.can_retry:
            return False, failure_report.retry_block_reason or "Failure analysis disallowed retry."

        return True, None

    def prepare_retry_attempt(
        self,
        current_attempt: int,
        context: RepairContext,
        failure_report: FailureAnalysisReport,
        previous_patch_hashes: List[str],
        custom_modified_contents: Optional[Dict[str, str]] = None,
    ) -> Tuple[RepairPlan, PatchResult, PatchRisk]:
        """Formulate next attempt's plan, patch, and risk evaluation.

        Next attempt requires:
        1. Current attempt < 3
        2. Non-identical patch hash
        3. Fresh static risk analysis
        4. Fresh human approval requirement
        """
        next_attempt_number = current_attempt + 1
        if next_attempt_number > self.MAX_ATTEMPTS:
            raise LoopLimitExceededError(
                f"Cannot create attempt {next_attempt_number}: maximum bound is {self.MAX_ATTEMPTS} attempts."
            )

        # 1. Augment context with verification failure
        augmented_failure = dict(context.failure)
        augmented_failure["verification_failure"] = failure_report.root_cause_summary
        augmented_failure["failure_signature"] = failure_report.failure_signature

        # 2. Formulate follow-up plan
        plan = self.planner.create_plan(
            context=context,
            custom_objective=f"Attempt {next_attempt_number}: Resolve verification regression - {failure_report.root_cause_summary}",
        )

        # 3. Generate new patch
        if custom_modified_contents:
            patch = self.patch_generator.generate_from_content_map(
                plan=plan,
                context=context,
                modified_contents=custom_modified_contents,
                explanation=f"Attempt {next_attempt_number} addressing verification failure.",
            )
        else:
            patch = self.patch_generator.generate_defensive_patch(plan=plan, context=context)

        # 4. Check patch difference (No progress check)
        if patch.patch_hash in previous_patch_hashes:
            raise NoProgressError(
                f"Generated retry patch hash '{patch.patch_hash[:8]}' is identical to previous attempt. No progress made."
            )

        # 5. Risk analysis on new patch
        risk = self.risk_analyzer.analyze(patch, plan, context)

        return plan, patch, risk
