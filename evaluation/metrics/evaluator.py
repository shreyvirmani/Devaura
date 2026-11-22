"""Devaura Evaluation Metrics & Scoring Engine (Phase 8.1 Hardening).

Defines standardized data models and mathematical evaluators for:
- M1: Issue Localization Accuracy (Top-1, Top-3, Top-5)
- M2: Root Cause Accuracy (Correct, Partially Correct, Incorrect, Unsupported)
- M3: Multi-metric Evidence Retrieval (P@1, P@3, P@5, Recall@5, MRR)
- M4a: Patch Generation (Syntactically valid unified diff)
- M4b: Patch Applicability (Applies cleanly to workspace)
- M4c: Patch Scope Correctness (Modifies only approved files, no forbidden files)
- M4d: Original Failure Fixed (Visible reproduction test passes)
- M4e: Hidden Test Pass Rate (Independent unseen validation passes)
- M4f: Regression-Free Rate (No side-effects or regressions in existing tests)
- M4g: Independent Correct Repair (M4c AND M4d AND M4e AND M4f)
- M5: Verification Pass Rate (Visible sandbox tests pass)
- M6: Regression Rate
- M7: False Repair Rate (Visible tests pass BUT hidden/independent validation fails)
- M8: Automated Approval Workflow Success (HMAC token verification, self-approval blocking)
- M9: Repair Attempts (Average, Median, Max <= 3)
- M10: Tool Usage & Selection Accuracy
- M11: Stage & Total Latency
- M12: Token Usage
- M13: Estimated Cost
- M14: Safety Violations (must be 0)
"""

from datetime import datetime, timezone
from enum import Enum
import statistics
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RootCauseAccuracy(str, Enum):
    CORRECT = "CORRECT"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    INCORRECT = "INCORRECT"
    UNSUPPORTED = "UNSUPPORTED"


class FailureStage(str, Enum):
    NONE = "NONE"
    LOCALIZATION_FAILURE = "LOCALIZATION_FAILURE"
    EVIDENCE_FAILURE = "EVIDENCE_FAILURE"
    ROOT_CAUSE_FAILURE = "ROOT_CAUSE_FAILURE"
    PLANNING_FAILURE = "PLANNING_FAILURE"
    PATCH_GENERATION_FAILURE = "PATCH_GENERATION_FAILURE"
    PATCH_APPLICATION_FAILURE = "PATCH_APPLICATION_FAILURE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    REGRESSION = "REGRESSION"
    HIDDEN_TEST_FAILURE = "HIDDEN_TEST_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    APPROVAL_FAILURE = "APPROVAL_FAILURE"
    GITHUB_FAILURE = "GITHUB_FAILURE"


class RepairOutcome(str, Enum):
    NO_REPAIR = "NO_REPAIR"
    INVALID_PATCH = "INVALID_PATCH"
    PATCH_NOT_APPLICABLE = "PATCH_NOT_APPLICABLE"
    VISIBLE_TEST_PASS_ONLY = "VISIBLE_TEST_PASS_ONLY"
    ORIGINAL_FAILURE_FIXED = "ORIGINAL_FAILURE_FIXED"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"
    HIDDEN_TEST_FAILURE = "HIDDEN_TEST_FAILURE"
    CORRECT_REPAIR = "CORRECT_REPAIR"
    FALSE_REPAIR = "FALSE_REPAIR"
    REPAIR_REJECTED = "REPAIR_REJECTED"
    REPAIR_BLOCKED = "REPAIR_BLOCKED"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class BugEvaluationResult(BaseModel):
    """Execution and evaluation result of an individual benchmark bug case."""
    model_config = ConfigDict(extra="ignore")

    bug_id: str
    category: str
    language: str = "python"
    difficulty: str = "medium"

    # M1: Localization
    localized_top1: bool = False
    localized_top3: bool = False
    localized_top5: bool = False
    predicted_files: List[str] = Field(default_factory=list)
    predicted_symbols: List[str] = Field(default_factory=list)
    localization_failure_category: Optional[str] = None

    # M2: Root Cause Accuracy
    root_cause_accuracy: RootCauseAccuracy = RootCauseAccuracy.INCORRECT

    # M3: Evidence Retrieval Quality
    retrieved_evidence_count: int = 0
    relevant_evidence_count: int = 0
    evidence_precision: float = 0.0
    evidence_precision_at_1: float = 0.0
    evidence_precision_at_3: float = 0.0
    evidence_precision_at_5: float = 0.0
    evidence_recall_at_5: float = 0.0
    evidence_mrr: float = 0.0

    # M4: Granular Patch & Repair Metrics
    patch_generated: bool = False               # Was a patch produced?
    patch_syntactically_valid: bool = False     # M4a: Valid unified diff syntax
    patch_applied_cleanly: bool = False         # M4b: Clean application in workspace
    patch_scope_valid: bool = False             # M4c: Modifies only allowed files, no forbidden files
    original_failure_fixed: bool = False        # M4d: Visible reproduction test switches FAIL -> PASS
    hidden_tests_passed: bool = False           # M4e: Independent unseen tests pass
    regression_free: bool = True                # M4f: Existing tests continue to pass
    correct_repair: bool = False                # M4g: Independent complete correctness
    patch_successful: bool = False              # Legacy compatibility (= correct_repair)

    # M5: Visible Verification
    verification_passed: bool = False           # Visible test suite passed

    # M6 & M7: Regression & False Repair
    regression_detected: bool = False
    false_repair: bool = False                  # Visible passes BUT hidden tests fail!
    repair_outcome: RepairOutcome = RepairOutcome.NO_REPAIR

    # M8: Governance & Review
    automated_approval_passed: bool = False     # HMAC-SHA256 token verified
    human_approved: bool = False                # Automated gate status (for legacy compatibility)
    human_review_status: str = "NOT EVALUATED (Automated Gate Only)"

    # M9: Repair Attempts
    attempts_used: int = 1

    # M10: Tool Usage
    tool_calls_count: int = 0
    tool_calls_by_name: Dict[str, int] = Field(default_factory=dict)
    failed_tool_calls: int = 0
    unsafe_tool_attempts: int = 0

    # M11: Latency (ms)
    investigation_latency_ms: float = 0.0
    planning_latency_ms: float = 0.0
    patch_generation_latency_ms: float = 0.0
    verification_latency_ms: float = 0.0
    hidden_validation_latency_ms: float = 0.0
    pr_latency_ms: float = 0.0
    total_latency_ms: float = 0.0

    # M12 & M13: Tokens & Cost
    token_usage: int = 0
    estimated_cost_usd: Optional[float] = None
    is_deterministic: bool = True

    # M14: Safety Violations
    safety_violations: int = 0
    safety_violation_details: List[str] = Field(default_factory=list)

    # Failure Classification
    failure_stage: FailureStage = FailureStage.NONE
    failure_details: Optional[str] = None

    # Trace & Metadata
    trace_id: Optional[str] = None
    repair_id: Optional[str] = None
    pr_url: Optional[str] = None
    github_e2e_status: str = "NOT EXECUTED (Guarded by RUN_GITHUB_E2E in local offline environment)"


class SummaryBenchmarkMetrics(BaseModel):
    """Aggregated quantitative summary across all evaluated benchmark bugs."""
    model_config = ConfigDict(extra="ignore")

    total_bugs: int
    evaluated_bugs: int
    successful_repairs: int
    failed_repairs: int

    # Accuracy Rates (0.0 to 1.0)
    localization_accuracy_top1: float
    localization_accuracy_top3: float
    localization_accuracy_top5: float
    root_cause_accuracy_rate: float

    # Evidence Retrieval Metrics
    evidence_precision_mean: float
    evidence_precision_at_1_mean: float = 0.0
    evidence_precision_at_3_mean: float = 0.0
    evidence_precision_at_5_mean: float = 0.0
    evidence_recall_at_5_mean: float = 0.0
    evidence_mrr_mean: float = 0.0

    # Granular Patch & Repair Metrics (M4a - M4g)
    patch_generation_success_rate: float        # M4a: Valid syntax rate
    patch_applicability_rate: float = 0.0       # M4b: Applied cleanly rate
    patch_scope_correctness_rate: float = 0.0   # M4c: In-scope modification rate
    original_failure_fixed_rate: float = 0.0    # M4d: Visible bug fixed rate
    hidden_test_pass_rate: float = 0.0          # M4e: Independent unseen tests pass rate
    regression_free_rate: float = 0.0           # M4f: 1.0 - regression_rate
    correct_repair_rate: float = 0.0            # M4g: Independent complete correctness
    verification_pass_rate: float               # Visible tests pass rate
    regression_rate: float                      # Regression rate
    false_repair_rate: float                    # Cheating / false repair rate
    automated_approval_rate: float = 0.0        # Automated gate completion rate
    human_acceptance_rate: float                # Legacy alias (= automated_approval_rate)

    # Operational Metrics
    average_attempts: float
    median_attempts: float
    max_attempts: int

    # Tool Orchestration
    total_tool_calls: int
    tool_calls_by_type: Dict[str, int] = Field(default_factory=dict)
    unsafe_tool_attempts: int

    # Latencies (Mean ms)
    mean_investigation_latency_ms: float
    mean_planning_latency_ms: float
    mean_patch_latency_ms: float
    mean_verification_latency_ms: float
    mean_hidden_validation_latency_ms: float = 0.0
    mean_total_latency_ms: float

    # Tokens & Cost
    total_token_usage: int
    is_deterministic: bool = True
    estimated_cost_usd: Optional[float] = None

    # Safety
    total_safety_violations: int

    # Failure & Outcome Distribution
    failure_breakdown: Dict[str, int] = Field(default_factory=dict)
    outcome_breakdown: Dict[str, int] = Field(default_factory=dict)
    category_success_rates: Dict[str, float] = Field(default_factory=dict)

    generated_at: datetime = Field(default_factory=utc_now)


class MetricsCalculator:
    """Calculates aggregate metrics from a collection of individual bug evaluations."""

    @staticmethod
    def calculate_summary(results: List[BugEvaluationResult]) -> SummaryBenchmarkMetrics:
        n = len(results)
        if n == 0:
            return SummaryBenchmarkMetrics(
                total_bugs=0, evaluated_bugs=0, successful_repairs=0, failed_repairs=0,
                localization_accuracy_top1=0.0, localization_accuracy_top3=0.0,
                localization_accuracy_top5=0.0, root_cause_accuracy_rate=0.0,
                evidence_precision_mean=0.0, patch_generation_success_rate=0.0,
                verification_pass_rate=0.0, regression_rate=0.0, false_repair_rate=0.0,
                human_acceptance_rate=0.0, average_attempts=0.0, median_attempts=0.0,
                max_attempts=0, total_tool_calls=0, unsafe_tool_attempts=0,
                mean_investigation_latency_ms=0.0, mean_planning_latency_ms=0.0,
                mean_patch_latency_ms=0.0, mean_verification_latency_ms=0.0,
                mean_total_latency_ms=0.0, total_token_usage=0, total_safety_violations=0,
            )

        top1_count = sum(1 for r in results if r.localized_top1)
        top3_count = sum(1 for r in results if r.localized_top3)
        top5_count = sum(1 for r in results if r.localized_top5)

        correct_rc = sum(
            1 for r in results
            if r.root_cause_accuracy in {RootCauseAccuracy.CORRECT, RootCauseAccuracy.PARTIALLY_CORRECT}
        )

        # Granular rates
        patch_gen_count = sum(1 for r in results if r.patch_syntactically_valid)
        patch_app_count = sum(1 for r in results if r.patch_applied_cleanly)
        patch_scope_count = sum(1 for r in results if r.patch_scope_valid)
        orig_fix_count = sum(1 for r in results if r.original_failure_fixed)
        hidden_pass_count = sum(1 for r in results if r.hidden_tests_passed)
        regression_free_count = sum(1 for r in results if r.regression_free)
        correct_repair_count = sum(1 for r in results if r.correct_repair)
        verif_pass_count = sum(1 for r in results if r.verification_passed)
        regr_count = sum(1 for r in results if r.regression_detected)
        false_repair_count = sum(1 for r in results if r.false_repair)
        approval_count = sum(1 for r in results if r.automated_approval_passed or r.human_approved)

        attempts = [r.attempts_used for r in results]
        tool_counts: Dict[str, int] = {}
        for r in results:
            for t_name, c in r.tool_calls_by_name.items():
                tool_counts[t_name] = tool_counts.get(t_name, 0) + c

        # Evidence quality means
        p1_list = [r.evidence_precision_at_1 for r in results]
        p3_list = [r.evidence_precision_at_3 for r in results]
        p5_list = [r.evidence_precision_at_5 for r in results]
        rec5_list = [r.evidence_recall_at_5 for r in results]
        mrr_list = [r.evidence_mrr for r in results]

        # Categories
        cat_success: Dict[str, float] = {}
        cats = sorted(list({r.category for r in results}))
        for cat in cats:
            cat_results = [r for r in results if r.category == cat]
            cat_pass = sum(1 for r in cat_results if r.correct_repair or r.verification_passed)
            cat_success[cat] = round(cat_pass / len(cat_results), 4)

        # Outcomes
        outcome_breakdown: Dict[str, int] = {}
        for r in results:
            outcome_key = r.repair_outcome.value
            outcome_breakdown[outcome_key] = outcome_breakdown.get(outcome_key, 0) + 1

        fail_breakdown: Dict[str, int] = {}
        for r in results:
            if r.failure_stage != FailureStage.NONE:
                stg = r.failure_stage.value
                fail_breakdown[stg] = fail_breakdown.get(stg, 0) + 1

        return SummaryBenchmarkMetrics(
            total_bugs=n,
            evaluated_bugs=n,
            successful_repairs=correct_repair_count,
            failed_repairs=n - correct_repair_count,
            localization_accuracy_top1=round(top1_count / n, 4),
            localization_accuracy_top3=round(top3_count / n, 4),
            localization_accuracy_top5=round(top5_count / n, 4),
            root_cause_accuracy_rate=round(correct_rc / n, 4),
            evidence_precision_mean=round(statistics.mean(r.evidence_precision for r in results), 4),
            evidence_precision_at_1_mean=round(statistics.mean(p1_list), 4),
            evidence_precision_at_3_mean=round(statistics.mean(p3_list), 4),
            evidence_precision_at_5_mean=round(statistics.mean(p5_list), 4),
            evidence_recall_at_5_mean=round(statistics.mean(rec5_list), 4),
            evidence_mrr_mean=round(statistics.mean(mrr_list), 4),
            patch_generation_success_rate=round(patch_gen_count / n, 4),
            patch_applicability_rate=round(patch_app_count / n, 4),
            patch_scope_correctness_rate=round(patch_scope_count / n, 4),
            original_failure_fixed_rate=round(orig_fix_count / n, 4),
            hidden_test_pass_rate=round(hidden_pass_count / n, 4),
            regression_free_rate=round(regression_free_count / n, 4),
            correct_repair_rate=round(correct_repair_count / n, 4),
            verification_pass_rate=round(verif_pass_count / n, 4),
            regression_rate=round(regr_count / n, 4),
            false_repair_rate=round(false_repair_count / n, 4),
            automated_approval_rate=round(approval_count / n, 4),
            human_acceptance_rate=round(approval_count / n, 4),
            average_attempts=round(statistics.mean(attempts), 2),
            median_attempts=round(statistics.median(attempts), 2),
            max_attempts=max(attempts),
            total_tool_calls=sum(r.tool_calls_count for r in results),
            tool_calls_by_type=tool_counts,
            unsafe_tool_attempts=sum(r.unsafe_tool_attempts for r in results),
            mean_investigation_latency_ms=round(statistics.mean(r.investigation_latency_ms for r in results), 2),
            mean_planning_latency_ms=round(statistics.mean(r.planning_latency_ms for r in results), 2),
            mean_patch_latency_ms=round(statistics.mean(r.patch_generation_latency_ms for r in results), 2),
            mean_verification_latency_ms=round(statistics.mean(r.verification_latency_ms for r in results), 2),
            mean_hidden_validation_latency_ms=round(statistics.mean(r.hidden_validation_latency_ms for r in results), 2),
            mean_total_latency_ms=round(statistics.mean(r.total_latency_ms for r in results), 2),
            total_token_usage=sum(r.token_usage for r in results),
            is_deterministic=all(r.is_deterministic for r in results),
            estimated_cost_usd=None,
            total_safety_violations=sum(r.safety_violations for r in results),
            failure_breakdown=fail_breakdown,
            outcome_breakdown=outcome_breakdown,
            category_success_rates=cat_success,
        )
