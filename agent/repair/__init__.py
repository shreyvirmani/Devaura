"""Devaura Phase 5 Repair Package."""

from agent.repair.models import (
    ApprovalStatus,
    CheckStatus,
    CheckType,
    FailureAnalysisReport,
    FailureClassification,
    FailureSignature,
    OverallVerificationStatus,
    PatchResult,
    PatchRisk,
    PatchRiskFinding,
    PatchRiskLevel,
    ProposedChange,
    RepairApproval,
    RepairAttemptInfo,
    RepairContext,
    RepairExecutionResult,
    RepairPlan,
    RepairState,
    TestFailure,
    VerificationCheck,
    VerificationRun,
    VerifiedRepairResult,
)
from agent.repair.state_machine import (
    InvalidRepairStateTransitionError,
    RepairStateMachine,
)
from agent.repair.context_builder import RepairContextBuilder
from agent.repair.planner import RepairPlanner
from agent.repair.patch_generator import (
    PatchGenerator,
    PatchScopeGuard,
    ScopeViolationError,
)
from agent.repair.risk_analyzer import PatchRiskAnalyzer
from agent.repair.approval_gate import (
    ApprovalRequiredError,
    HumanApprovalGate,
    PatchIntegrityError,
)
from agent.repair.loop_coordinator import (
    LoopLimitExceededError,
    NoProgressError,
    RepairLoopCoordinator,
)

__all__ = [
    "ApprovalStatus",
    "CheckStatus",
    "CheckType",
    "FailureAnalysisReport",
    "FailureClassification",
    "FailureSignature",
    "OverallVerificationStatus",
    "PatchResult",
    "PatchRisk",
    "PatchRiskFinding",
    "PatchRiskLevel",
    "ProposedChange",
    "RepairApproval",
    "RepairAttemptInfo",
    "RepairContext",
    "RepairExecutionResult",
    "RepairPlan",
    "RepairState",
    "TestFailure",
    "VerificationCheck",
    "VerificationRun",
    "VerifiedRepairResult",
    "InvalidRepairStateTransitionError",
    "RepairStateMachine",
    "RepairContextBuilder",
    "RepairPlanner",
    "PatchGenerator",
    "PatchScopeGuard",
    "ScopeViolationError",
    "PatchRiskAnalyzer",
    "ApprovalRequiredError",
    "HumanApprovalGate",
    "PatchIntegrityError",
    "LoopLimitExceededError",
    "NoProgressError",
    "RepairLoopCoordinator",
]
