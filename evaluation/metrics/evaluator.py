"""Devaura Evaluation Metrics & Scoring Engine (Phase 8).

Defines standardized data models and mathematical evaluators for:
- M1: Issue Localization Accuracy (Top-1, Top-3, Top-5)
- M2: Root Cause Accuracy (Correct, Partially Correct, Incorrect, Unsupported)
- M3: Evidence Retrieval Precision
- M4: Patch Success Rate
- M5: Verification Pass Rate
- M6: Regression Rate
- M7: False Repair Rate
- M8: Human Acceptance Rate
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
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    APPROVAL_FAILURE = "APPROVAL_FAILURE"
    GITHUB_FAILURE = "GITHUB_FAILURE"


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

    # M2: Root Cause Accuracy
    root_cause_accuracy: RootCauseAccuracy = RootCauseAccuracy.INCORRECT

    # M3: Evidence Retrieval Precision
    retrieved_evidence_count: int = 0
    relevant_evidence_count: int = 0
    evidence_precision: float = 0.0

    # M4 & M5: Patch & Verification
    patch_generated: bool = False
    patch_syntactically_valid: bool = False
    patch_applied_cleanly: bool = False
    verification_passed: bool = False
    patch_successful: bool = False

    # M6 & M7: Regression & False Repair
    regression_detected: bool = False
    false_repair: bool = False

    # M8: Human Acceptance
    human_approved: bool = False

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
    evidence_precision_mean: float
    patch_generation_success_rate: float
    verification_pass_rate: float
    regression_rate: float
    false_repair_rate: float
    human_acceptance_rate: float

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
    mean_total_latency_ms: float

    # Tokens & Cost
    total_token_usage: int
    is_deterministic: bool = True
    estimated_cost_usd: Optional[float] = None

    # Safety
    total_safety_violations: int

    # Failure Distribution
    failure_breakdown: Dict[str, int] = Field(default_factory=dict)
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

        rc_correct = sum(1 for r in results if r.root_cause_accuracy == RootCauseAccuracy.CORRECT)
        ev_prec_mean = statistics.mean(r.evidence_precision for r in results) if results else 0.0

        patches_gen = sum(1 for r in results if r.patch_generated)
        verified = sum(1 for r in results if r.verification_passed)
        regressions = sum(1 for r in results if r.regression_detected)
        false_repairs = sum(1 for r in results if r.false_repair)
        human_accepted = sum(1 for r in results if r.human_approved)

        attempts_list = [r.attempts_used for r in results]
        avg_attempts = statistics.mean(attempts_list) if attempts_list else 0.0
        med_attempts = statistics.median(attempts_list) if attempts_list else 0.0
        max_attempts = max(attempts_list) if attempts_list else 0

        total_tools = sum(r.tool_calls_count for r in results)
        unsafe_tools = sum(r.unsafe_tool_attempts for r in results)
        violations = sum(r.safety_violations for r in results)

        tool_breakdown: Dict[str, int] = {}
        for r in results:
            for k, v in r.tool_calls_by_name.items():
                tool_breakdown[k] = tool_breakdown.get(k, 0) + v

        failure_counts: Dict[str, int] = {}
        for r in results:
            if r.failure_stage != FailureStage.NONE:
                failure_counts[r.failure_stage.value] = failure_counts.get(r.failure_stage.value, 0) + 1

        # Per Category success rates
        categories = sorted(list({r.category for r in results}))
        cat_success: Dict[str, float] = {}
        for cat in categories:
            cat_results = [r for r in results if r.category == cat]
            cat_success[cat] = round(
                sum(1 for r in cat_results if r.verification_passed) / len(cat_results), 4
            )

        return SummaryBenchmarkMetrics(
            total_bugs=n,
            evaluated_bugs=n,
            successful_repairs=verified,
            failed_repairs=n - verified,
            localization_accuracy_top1=round(top1_count / n, 4),
            localization_accuracy_top3=round(top3_count / n, 4),
            localization_accuracy_top5=round(top5_count / n, 4),
            root_cause_accuracy_rate=round(rc_correct / n, 4),
            evidence_precision_mean=round(ev_prec_mean, 4),
            patch_generation_success_rate=round(patches_gen / n, 4),
            verification_pass_rate=round(verified / n, 4),
            regression_rate=round(regressions / max(1, verified), 4),
            false_repair_rate=round(false_repairs / max(1, patches_gen), 4),
            human_acceptance_rate=round(human_accepted / max(1, verified), 4),
            average_attempts=round(avg_attempts, 2),
            median_attempts=round(med_attempts, 2),
            max_attempts=max_attempts,
            total_tool_calls=total_tools,
            tool_calls_by_type=tool_breakdown,
            unsafe_tool_attempts=unsafe_tools,
            mean_investigation_latency_ms=round(statistics.mean(r.investigation_latency_ms for r in results), 2),
            mean_planning_latency_ms=round(statistics.mean(r.planning_latency_ms for r in results), 2),
            mean_patch_latency_ms=round(statistics.mean(r.patch_generation_latency_ms for r in results), 2),
            mean_verification_latency_ms=round(statistics.mean(r.verification_latency_ms for r in results), 2),
            mean_total_latency_ms=round(statistics.mean(r.total_latency_ms for r in results), 2),
            total_token_usage=sum(r.token_usage for r in results),
            is_deterministic=all(r.is_deterministic for r in results),
            estimated_cost_usd=None,
            total_safety_violations=violations,
            failure_breakdown=failure_counts,
            category_success_rates=cat_success,
        )
