"""Devaura Phase 5 Repair Package."""

from agent.repair.models import (
    ApprovalStatus,
    PatchResult,
    PatchRisk,
    PatchRiskFinding,
    PatchRiskLevel,
    ProposedChange,
    RepairApproval,
    RepairContext,
    RepairExecutionResult,
    RepairPlan,
    RepairState,
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

__all__ = [
    "ApprovalStatus",
    "PatchResult",
    "PatchRisk",
    "PatchRiskFinding",
    "PatchRiskLevel",
    "ProposedChange",
    "RepairApproval",
    "RepairContext",
    "RepairExecutionResult",
    "RepairPlan",
    "RepairState",
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
]
