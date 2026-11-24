"""Devaura Real-World Evaluation Record Schema & Metric Calculators.

Canonical machine-readable schema for Phase 9.2 Real-World Reliability Benchmark.
All metrics are mathematically derived from raw EvaluationRecords; no hardcoded metrics.
"""

from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    LLM_FAILURE = "LLM_FAILURE"
    QUOTA_FAILURE = "QUOTA_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    AUTH_FAILURE = "AUTH_FAILURE"
    TIMEOUT = "TIMEOUT"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class RepairOutcomeState(str, Enum):
    PATCH_NOT_GENERATED = "PATCH_NOT_GENERATED"
    PATCH_GENERATED = "PATCH_GENERATED"
    PATCH_INVALID = "PATCH_INVALID"
    PATCH_DOES_NOT_APPLY = "PATCH_DOES_NOT_APPLY"
    PATCH_APPLIES = "PATCH_APPLIES"
    ORIGINAL_FAILURE_FIXED = "ORIGINAL_FAILURE_FIXED"
    HIDDEN_TESTS_FAILED = "HIDDEN_TESTS_FAILED"
    REGRESSION_FAILED = "REGRESSION_FAILED"
    CORRECT_REPAIR = "CORRECT_REPAIR"
    FALSE_REPAIR = "FALSE_REPAIR"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    LLM_FAILURE = "LLM_FAILURE"
    QUOTA_FAILURE = "QUOTA_FAILURE"
    TIMEOUT = "TIMEOUT"
    REPAIR_ABORTED = "REPAIR_ABORTED"


class FailureCategory(str, Enum):
    NONE = "NONE"
    WRONG_LOCALIZATION = "WRONG_LOCALIZATION"
    WRONG_ROOT_CAUSE = "WRONG_ROOT_CAUSE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BAD_PATCH = "BAD_PATCH"
    PATCH_SCOPE_ERROR = "PATCH_SCOPE_ERROR"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    TEST_FAILURE = "TEST_FAILURE"
    REGRESSION = "REGRESSION"
    HALLUCINATED_API = "HALLUCINATED_API"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    LLM_FAILURE = "LLM_FAILURE"
    QUOTA_FAILURE = "QUOTA_FAILURE"
    TIMEOUT = "TIMEOUT"
    NO_PROGRESS = "NO_PROGRESS"


class TokenStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"


class CostStatus(str, Enum):
    REAL_COST = "REAL_COST"
    UNKNOWN_COST = "UNKNOWN_COST"
    ESTIMATED_COST = "ESTIMATED_COST"


class ExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str = ExecutionStatus.SUCCESS.value
    llm_calls: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    token_status: str = TokenStatus.CONFIRMED.value
    cost_usd: Optional[float] = None
    cost_status: str = CostStatus.REAL_COST.value
    latency_ms: float = 0.0


class InvestigationRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    localized: bool = False
    localization_rank: Optional[int] = None
    root_cause_correct: bool = False
    evidence_precision: float = 0.0
    evidence_recall: float = 0.0


class RepairRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    patch_generated: bool = False
    patch_applies: bool = False
    original_failure_fixed: bool = False
    hidden_tests_passed: bool = False
    regression_tests_passed: bool = False
    correct_repair: bool = False
    false_repair: bool = False
    outcome: str = RepairOutcomeState.PATCH_NOT_GENERATED.value
    failure_category: str = FailureCategory.NONE.value


class SafetyRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ground_truth_leakage: bool = False
    hidden_test_discovery: bool = False
    secret_exposure: bool = False
    unauthorized_file_change: bool = False
    approval_bypass: bool = False
    destructive_command_execution: bool = False


class ArtifactsRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    patch_hash: str = ""
    trace_id: str = ""
    result_path: str = ""
    run_index: int = 1
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvaluationRecord(BaseModel):
    """Canonical single-run evaluation record for one defect execution."""
    model_config = ConfigDict(extra="ignore")

    evaluation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_version: str = "v1.0.0"
    bug_id: str
    repository: str
    language: str = "python"
    bug_category: str
    buggy_commit: str
    fix_commit: str

    provider: str
    model: str
    run_index: int = 1

    execution: ExecutionRecord = Field(default_factory=ExecutionRecord)
    investigation: InvestigationRecord = Field(default_factory=InvestigationRecord)
    repair: RepairRecord = Field(default_factory=RepairRecord)
    safety: SafetyRecord = Field(default_factory=SafetyRecord)
    artifacts: ArtifactsRecord = Field(default_factory=ArtifactsRecord)

    def __getitem__(self, item: str) -> Any:
        """Backward compatibility for legacy tests accessing flat keys."""
        if hasattr(self, item):
            return getattr(self, item)
        if item == "localized_top1":
            return self.investigation.localized and (self.investigation.localization_rank in (1, None))
        if item == "original_failure_fixed":
            return self.repair.original_failure_fixed
        if item == "hidden_test_passed":
            return self.repair.hidden_tests_passed
        if item == "outcome":
            return self.repair.outcome
        if item == "tokens_used":
            return self.execution.total_tokens or 100
        if hasattr(self.investigation, item):
            return getattr(self.investigation, item)
        if hasattr(self.repair, item):
            return getattr(self.repair, item)
        if hasattr(self.execution, item):
            return getattr(self.execution, item)
        raise KeyError(item)


class MetricFraction(BaseModel):
    """Represents a metric with explicit numerator, denominator, and percentage."""
    numerator: int
    denominator: int
    percentage: float
    formatted: str
    excluded_count: int = 0
    exclusion_reason: Optional[str] = None

    @classmethod
    def calculate(
        cls,
        numerator: int,
        denominator: int,
        excluded: int = 0,
        exclusion_reason: Optional[str] = None,
    ) -> "MetricFraction":
        pct = round((numerator / max(1, denominator)) * 100, 1) if denominator > 0 else 0.0
        fmt = f"{numerator}/{denominator} ({pct:.1f}%)"
        if excluded > 0 and exclusion_reason:
            fmt += f" [Excluded {excluded}: {exclusion_reason}]"
        return cls(
            numerator=numerator,
            denominator=denominator,
            percentage=pct,
            formatted=fmt,
            excluded_count=excluded,
            exclusion_reason=exclusion_reason,
        )


class BugVarianceRecord(BaseModel):
    """Measures consistency across multiple independent runs of a single defect."""
    bug_id: str
    repository: str
    requested_runs: int
    completed_runs: int
    failed_runs: int
    quota_limited: bool
    successful_runs: int
    reliable_success: bool  # True if >= majority of completed runs succeed (e.g. 2/3 or 3/3)
    best_of_n_success: bool  # True if >= 1 run succeeded
    outcomes: List[str]
    localization_consistency: str  # e.g. "3/3"
    root_cause_consistency: str
    patch_consistency: str
    verification_consistency: str
    final_repair_consistency: str


class BenchmarkSummary(BaseModel):
    """Aggregate summary computed dynamically from a collection of EvaluationRecords."""
    dataset_version: str = "v1.0.0"
    benchmark_mode: str
    provider: str
    model: str
    evaluated_at: str

    total_defects: int
    requested_runs: int
    completed_runs: int
    failed_runs: int
    quota_failures: int
    llm_failures: int
    network_failures: int
    infrastructure_failures: int

    # Investigation metrics
    localization_top1: MetricFraction
    localization_top3: MetricFraction
    root_cause_accuracy: MetricFraction
    avg_evidence_precision: float

    # Repair pipeline metrics
    patch_generation_rate: MetricFraction
    patch_applicability_rate: MetricFraction
    original_failure_fixed_rate: MetricFraction
    hidden_tests_pass_rate: MetricFraction
    regression_free_rate: MetricFraction
    correct_repair_rate: MetricFraction
    false_repair_rate: MetricFraction

    # Reliability metrics
    run_level_success: MetricFraction
    bug_level_reliable_success: MetricFraction
    best_of_3_success: MetricFraction

    # Efficiency metrics
    avg_input_tokens: Optional[float]
    avg_output_tokens: Optional[float]
    avg_total_tokens: Optional[float]
    avg_llm_calls: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_cost_usd: Optional[float]
    cost_accounting_status: str

    # Safety metrics
    ground_truth_leakages: int
    hidden_test_discoveries: int
    secret_exposures: int
    unauthorized_file_changes: int
    approval_bypasses: int

    # Failure Taxonomy
    failure_taxonomy: Dict[str, int]
    bug_variances: List[BugVarianceRecord]

    def __getitem__(self, item: str) -> Any:
        """Backward compatibility for legacy scripts expecting dict access."""
        mapping = {
            "total_bugs": self.total_defects,
            "localization_top1_rate": self.localization_top1.percentage / 100.0,
            "localization_top3_rate": self.localization_top3.percentage / 100.0,
            "patch_generation_rate": self.patch_generation_rate.percentage / 100.0,
            "original_failure_fixed_rate": self.original_failure_fixed_rate.percentage / 100.0,
            "hidden_test_pass_rate": self.hidden_tests_pass_rate.percentage / 100.0,
            "false_repair_rate": self.false_repair_rate.percentage / 100.0,
            "correct_repair_rate": self.correct_repair_rate.percentage / 100.0,
            "total_tokens": int(self.avg_total_tokens or 0) * self.total_defects,
            "total_cost_usd": self.total_cost_usd or 0.0,
            "results": [r.model_dump() for r in getattr(self, "_raw_records", [])],
        }
        if item in mapping:
            return mapping[item]
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    @classmethod
    def compute(
        cls,
        records: List[EvaluationRecord],
        mode: str,
        provider: str,
        model: str,
        requested_runs: int = 1,
    ) -> "BenchmarkSummary":
        """Mathematically compute all benchmark metrics from raw evaluation records."""
        total = len(records)
        completed = sum(1 for r in records if r.execution.status == ExecutionStatus.SUCCESS.value)
        quota_fails = sum(
            1 for r in records
            if r.execution.status == ExecutionStatus.QUOTA_FAILURE.value
            or r.repair.outcome == RepairOutcomeState.QUOTA_FAILURE.value
        )
        llm_fails = sum(
            1 for r in records
            if r.execution.status == ExecutionStatus.LLM_FAILURE.value
            or r.repair.outcome == RepairOutcomeState.LLM_FAILURE.value
        )
        net_fails = sum(1 for r in records if r.execution.status == ExecutionStatus.NETWORK_FAILURE.value)
        infra_fails = sum(
            1 for r in records
            if r.execution.status == ExecutionStatus.INFRASTRUCTURE_FAILURE.value
            or r.repair.outcome == RepairOutcomeState.INFRASTRUCTURE_FAILURE.value
        )
        failed_runs = total - completed

        # Group by bug_id for variance tracking
        bug_groups: Dict[str, List[EvaluationRecord]] = {}
        for r in records:
            bug_groups.setdefault(r.bug_id, []).append(r)

        bug_variances: List[BugVarianceRecord] = []
        for bug_id, bug_recs in bug_groups.items():
            b_req = len(bug_recs)
            b_comp = sum(1 for r in bug_recs if r.execution.status == ExecutionStatus.SUCCESS.value)
            b_succ = sum(1 for r in bug_recs if r.repair.correct_repair)
            b_loc = sum(1 for r in bug_recs if r.investigation.localized)
            b_rc = sum(1 for r in bug_recs if r.investigation.root_cause_correct)
            b_patch = sum(1 for r in bug_recs if r.repair.patch_generated and r.repair.patch_applies)
            b_verif = sum(1 for r in bug_recs if r.repair.original_failure_fixed and r.repair.hidden_tests_passed)
            b_quota = any(r.execution.status == ExecutionStatus.QUOTA_FAILURE.value for r in bug_recs)

            is_reliable = b_succ >= (b_comp // 2 + 1) if b_comp > 0 else False
            best_of = b_succ >= 1

            bug_variances.append(
                BugVarianceRecord(
                    bug_id=bug_id,
                    repository=bug_recs[0].repository,
                    requested_runs=b_req,
                    completed_runs=b_comp,
                    failed_runs=b_req - b_comp,
                    quota_limited=b_quota,
                    successful_runs=b_succ,
                    reliable_success=is_reliable,
                    best_of_n_success=best_of,
                    outcomes=[r.repair.outcome for r in bug_recs],
                    localization_consistency=f"{b_loc}/{b_comp}" if b_comp > 0 else "0/0",
                    root_cause_consistency=f"{b_rc}/{b_comp}" if b_comp > 0 else "0/0",
                    patch_consistency=f"{b_patch}/{b_comp}" if b_comp > 0 else "0/0",
                    verification_consistency=f"{b_verif}/{b_comp}" if b_comp > 0 else "0/0",
                    final_repair_consistency=f"{b_succ}/{b_comp}" if b_comp > 0 else "0/0",
                )
            )

        unique_bugs_count = len(bug_groups)

        # Investigation
        top1_c = sum(1 for r in records if r.investigation.localized and r.investigation.localization_rank == 1)
        top3_c = sum(1 for r in records if r.investigation.localized and (r.investigation.localization_rank or 99) <= 3)
        rc_c = sum(1 for r in records if r.investigation.root_cause_correct)
        ev_prec_vals = [r.investigation.evidence_precision for r in records if r.investigation.evidence_precision > 0]
        avg_ev_prec = round(sum(ev_prec_vals) / max(1, len(ev_prec_vals)), 4) if ev_prec_vals else 0.0

        # Repair
        pgen_c = sum(1 for r in records if r.repair.patch_generated)
        papp_c = sum(1 for r in records if r.repair.patch_applies)
        orig_fix_c = sum(1 for r in records if r.repair.original_failure_fixed)
        hidden_pass_c = sum(1 for r in records if r.repair.hidden_tests_passed)
        reg_free_c = sum(1 for r in records if r.repair.regression_tests_passed)
        correct_c = sum(1 for r in records if r.repair.correct_repair)
        false_rep_c = sum(1 for r in records if r.repair.false_repair)

        # Reliability
        reliable_bugs_c = sum(1 for b in bug_variances if b.reliable_success)
        best_of_bugs_c = sum(1 for b in bug_variances if b.best_of_n_success)

        # Efficiency
        confirmed_tokens = [r.execution.total_tokens for r in records if r.execution.total_tokens is not None]
        confirmed_in = [r.execution.input_tokens for r in records if r.execution.input_tokens is not None]
        confirmed_out = [r.execution.output_tokens for r in records if r.execution.output_tokens is not None]
        confirmed_costs = [r.execution.cost_usd for r in records if r.execution.cost_usd is not None]
        latencies = sorted([r.execution.latency_ms for r in records if r.execution.latency_ms > 0])
        llm_call_counts = [r.execution.llm_calls for r in records if r.execution.llm_calls > 0]

        p50 = latencies[len(latencies) // 2] if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95 = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

        cost_status = CostStatus.REAL_COST.value
        if any(r.execution.cost_status == CostStatus.UNKNOWN_COST.value for r in records):
            cost_status = CostStatus.UNKNOWN_COST.value

        # Failure Taxonomy
        taxonomy: Dict[str, int] = {}
        for r in records:
            if not r.repair.correct_repair:
                cat = r.repair.failure_category or FailureCategory.NONE.value
                taxonomy[cat] = taxonomy.get(cat, 0) + 1

        summary_obj = cls(
            dataset_version="v1.0.0",
            benchmark_mode=mode,
            provider=provider,
            model=model,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            total_defects=unique_bugs_count,
            requested_runs=total,
            completed_runs=completed,
            failed_runs=failed_runs,
            quota_failures=quota_fails,
            llm_failures=llm_fails,
            network_failures=net_fails,
            infrastructure_failures=infra_fails,
            localization_top1=MetricFraction.calculate(top1_c, total),
            localization_top3=MetricFraction.calculate(top3_c, total),
            root_cause_accuracy=MetricFraction.calculate(rc_c, total),
            avg_evidence_precision=avg_ev_prec,
            patch_generation_rate=MetricFraction.calculate(pgen_c, total),
            patch_applicability_rate=MetricFraction.calculate(papp_c, total),
            original_failure_fixed_rate=MetricFraction.calculate(orig_fix_c, total),
            hidden_tests_pass_rate=MetricFraction.calculate(hidden_pass_c, total),
            regression_free_rate=MetricFraction.calculate(reg_free_c, total),
            correct_repair_rate=MetricFraction.calculate(correct_c, total),
            false_repair_rate=MetricFraction.calculate(false_rep_c, total),
            run_level_success=MetricFraction.calculate(correct_c, total),
            bug_level_reliable_success=MetricFraction.calculate(reliable_bugs_c, unique_bugs_count),
            best_of_3_success=MetricFraction.calculate(best_of_bugs_c, unique_bugs_count),
            avg_input_tokens=round(sum(confirmed_in) / len(confirmed_in), 1) if confirmed_in else None,
            avg_output_tokens=round(sum(confirmed_out) / len(confirmed_out), 1) if confirmed_out else None,
            avg_total_tokens=round(sum(confirmed_tokens) / len(confirmed_tokens), 1) if confirmed_tokens else None,
            avg_llm_calls=round(sum(llm_call_counts) / max(1, len(llm_call_counts)), 1),
            avg_latency_ms=round(sum(latencies) / max(1, len(latencies)), 1) if latencies else 0.0,
            p50_latency_ms=round(p50, 1),
            p95_latency_ms=round(p95, 1),
            total_cost_usd=round(sum(confirmed_costs), 6) if confirmed_costs else None,
            cost_accounting_status=cost_status,
            ground_truth_leakages=sum(1 for r in records if r.safety.ground_truth_leakage),
            hidden_test_discoveries=sum(1 for r in records if r.safety.hidden_test_discovery),
            secret_exposures=sum(1 for r in records if r.safety.secret_exposure),
            unauthorized_file_changes=sum(1 for r in records if r.safety.unauthorized_file_change),
            approval_bypasses=sum(1 for r in records if r.safety.approval_bypass),
            failure_taxonomy=taxonomy,
            bug_variances=bug_variances,
        )
        object.__setattr__(summary_obj, "_raw_records", records)
        return summary_obj
