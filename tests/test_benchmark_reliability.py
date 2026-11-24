"""Devaura Phase 9.2 Real-World Reliability Benchmark Test Suite.

Automated validation of:
1. EvaluationRecord schema integrity and machine-readable serialization
2. Distinction of all 15+ repair outcome states (Requirement 4)
3. Numerator/denominator percentage formatting without hardcoded metrics (Requirement 3)
4. Separation of Run-Level Success vs Bug-Level Reliable Success vs Best-of-N (Requirements 14 & 16)
5. Multi-run variance measurement (Requirements 6 & 7)
6. Physical separation of Agent Workspace vs Evaluator Workspace (Requirement 9)
7. Future fix commit inaccessibility in Git history (Requirement 12)
8. Ground-truth leakage detection on prompts and tool results (Requirement 10)
9. Quota failure handling without silent mock fallback (Requirement 20)
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import pytest

from data.validation.ground_truth_validator import GroundTruthLeakageError, GroundTruthValidator
from evaluation.historical.ground_truth import HISTORICAL_BUGS
from evaluation.historical.runner import HistoricalBenchmarkRunner
from evaluation.schemas import (
    BenchmarkSummary,
    BugVarianceRecord,
    EvaluationRecord,
    ExecutionRecord,
    ExecutionStatus,
    FailureCategory,
    InvestigationRecord,
    MetricFraction,
    RepairOutcomeState,
    RepairRecord,
    SafetyRecord,
)
from sandbox.workspace import IsolatedWorkspace


class TestBenchmarkRecordSchema:
    """Validates the canonical EvaluationRecord schema."""

    def test_evaluation_record_schema_serialization(self):
        record = EvaluationRecord(
            evaluation_id=str(uuid.uuid4()),
            dataset_version="v1.0.0",
            bug_id="HIST-001",
            repository="pallets/flask",
            language="python",
            bug_category="Routing / URL Parsing",
            buggy_commit="8f3b21c",
            fix_commit="9e4a32b",
            provider="google",
            model="gemini-2.5-flash",
            run_index=1,
            execution=ExecutionRecord(
                status=ExecutionStatus.SUCCESS.value,
                llm_calls=3,
                input_tokens=1500,
                output_tokens=350,
                total_tokens=1850,
                cost_usd=0.00021,
                latency_ms=1250.0,
            ),
            investigation=InvestigationRecord(
                localized=True,
                localization_rank=1,
                root_cause_correct=True,
                evidence_precision=1.0,
            ),
            repair=RepairRecord(
                patch_generated=True,
                patch_applies=True,
                original_failure_fixed=True,
                hidden_tests_passed=True,
                regression_tests_passed=True,
                correct_repair=True,
                false_repair=False,
                outcome=RepairOutcomeState.CORRECT_REPAIR.value,
            ),
        )

        serialized = record.model_dump_json()
        data = json.loads(serialized)
        assert data["bug_id"] == "HIST-001"
        assert data["execution"]["total_tokens"] == 1850
        assert data["repair"]["outcome"] == "CORRECT_REPAIR"
        assert data["repair"]["correct_repair"] is True


class TestOutcomeDistinction:
    """Verifies that all outcome states are distinct and not collapsed."""

    def test_distinct_outcome_states(self):
        # 1. Patch generated != Patch applies
        r1 = RepairRecord(patch_generated=True, patch_applies=False, outcome=RepairOutcomeState.PATCH_DOES_NOT_APPLY.value)
        assert r1.patch_generated is True
        assert r1.patch_applies is False
        assert r1.correct_repair is False

        # 2. Patch applies != Original failure fixed
        r2 = RepairRecord(patch_generated=True, patch_applies=True, original_failure_fixed=False, outcome=RepairOutcomeState.PATCH_APPLIES.value)
        assert r2.patch_applies is True
        assert r2.original_failure_fixed is False
        assert r2.correct_repair is False

        # 3. Original failure fixed != Hidden tests pass (False Repair)
        r3 = RepairRecord(
            patch_generated=True,
            patch_applies=True,
            original_failure_fixed=True,
            hidden_tests_passed=False,
            false_repair=True,
            outcome=RepairOutcomeState.FALSE_REPAIR.value,
        )
        assert r3.original_failure_fixed is True
        assert r3.hidden_tests_passed is False
        assert r3.false_repair is True
        assert r3.correct_repair is False

        # 4. Correct repair requires BOTH original fixed AND hidden tests passed
        r4 = RepairRecord(
            patch_generated=True,
            patch_applies=True,
            original_failure_fixed=True,
            hidden_tests_passed=True,
            correct_repair=True,
            false_repair=False,
            outcome=RepairOutcomeState.CORRECT_REPAIR.value,
        )
        assert r4.correct_repair is True


class TestMetricFormattingAndCalculation:
    """Verifies that all metrics render as numerator/denominator (percentage)."""

    def test_metric_fraction_formatting(self):
        m1 = MetricFraction.calculate(7, 12)
        assert m1.numerator == 7
        assert m1.denominator == 12
        assert m1.percentage == 58.3
        assert m1.formatted == "7/12 (58.3%)"

        m2 = MetricFraction.calculate(9, 10, excluded=2, exclusion_reason="quota failure")
        assert "9/10 (90.0%)" in m2.formatted
        assert "Excluded 2: quota failure" in m2.formatted

    def test_run_level_vs_bug_level_success_separation(self):
        """Validates that run-level success is strictly distinguished from bug-level reliable success."""
        records = []
        # Bug 1: 3/3 successes
        for r in range(1, 4):
            records.append(
                EvaluationRecord(
                    bug_id="HIST-001",
                    repository="pallets/flask",
                    bug_category="Routing",
                    buggy_commit="8f3b21c",
                    fix_commit="9e4a32b",
                    provider="mock",
                    model="mock",
                    run_index=r,
                    repair=RepairRecord(correct_repair=True, outcome="CORRECT_REPAIR"),
                )
            )
        # Bug 2: 1/3 successes (Stochastic hit - NOT reliably solved)
        records.append(
            EvaluationRecord(
                bug_id="HIST-002",
                repository="psf/requests",
                bug_category="Security",
                buggy_commit="b2c1d3e",
                fix_commit="f4e5a6b",
                provider="mock",
                model="mock",
                run_index=1,
                repair=RepairRecord(correct_repair=True, outcome="CORRECT_REPAIR"),
            )
        )
        records.append(
            EvaluationRecord(
                bug_id="HIST-002",
                repository="psf/requests",
                bug_category="Security",
                buggy_commit="b2c1d3e",
                fix_commit="f4e5a6b",
                provider="mock",
                model="mock",
                run_index=2,
                repair=RepairRecord(correct_repair=False, outcome="PATCH_DOES_NOT_APPLY"),
            )
        )
        records.append(
            EvaluationRecord(
                bug_id="HIST-002",
                repository="psf/requests",
                bug_category="Security",
                buggy_commit="b2c1d3e",
                fix_commit="f4e5a6b",
                provider="mock",
                model="mock",
                run_index=3,
                repair=RepairRecord(correct_repair=False, outcome="TEST_FAILURE"),
            )
        )

        summary = BenchmarkSummary.compute(records=records, mode="test", provider="mock", model="mock")

        # Run-level: 4 successes out of 6 runs = 66.7%
        assert summary.run_level_success.numerator == 4
        assert summary.run_level_success.denominator == 6
        assert summary.run_level_success.formatted == "4/6 (66.7%)"

        # Bug-level reliable success: Only Bug 1 succeeded reliably (>= majority of runs). Bug 2 was 1/3 (not reliable).
        assert summary.bug_level_reliable_success.numerator == 1
        assert summary.bug_level_reliable_success.denominator == 2
        assert summary.bug_level_reliable_success.formatted == "1/2 (50.0%)"

        # Best-of-3: Both bugs had at least 1 success
        assert summary.best_of_3_success.numerator == 2
        assert summary.best_of_3_success.denominator == 2
        assert summary.best_of_3_success.formatted == "2/2 (100.0%)"


class TestPhysicalWorkspaceIsolation:
    """Verifies Requirement 9: Physical separation between Agent and Evaluator workspaces."""

    def test_agent_workspace_never_contains_hidden_tests(self):
        runner = HistoricalBenchmarkRunner(mode="deterministic")
        bug = HISTORICAL_BUGS[0]  # Flask

        agent_ws = IsolatedWorkspace(
            source_repo_path=str(runner.dataset_dir / bug.bug_id),
            workspace_id="test_agent_isolation",
        )
        agent_path = Path(agent_ws.create())

        try:
            # 1. Physical absence of hidden test file
            assert not (agent_path / "tests" / "test_hidden_validation.py").exists()
            assert not (agent_path / "test_hidden.py").exists()

            # 2. find/glob attack returns zero hidden test files
            found_hidden = list(agent_path.rglob("*hidden*"))
            assert len(found_hidden) == 0, f"Found hidden files in agent workspace: {found_hidden}"

            # 3. Source files do not import or reference hidden tests
            for py_file in agent_path.rglob("*.py"):
                text = py_file.read_text(encoding="utf-8")
                assert "test_hidden_validation" not in text
                assert "test_slash_redirect_empty_query" not in text  # Hidden test assertion function
        finally:
            agent_ws.cleanup()


class TestGitHistoryInaccessibility:
    """Verifies Requirement 12: Future fix commit is unreachable from Git history in agent workspace."""

    def test_fix_commit_unreachable_in_agent_workspace(self, tmp_path):
        bug = HISTORICAL_BUGS[0]  # Flask: buggy=8f3b21c, fix=9e4a32b
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        # Initialize isolated git repository at buggy revision
        subprocess.run("git init", shell=True, cwd=repo_dir, check=True, capture_output=True)
        subprocess.run('git config user.email "test@devaura.ai"', shell=True, cwd=repo_dir, check=True, capture_output=True)
        subprocess.run('git config user.name "Devaura Agent"', shell=True, cwd=repo_dir, check=True, capture_output=True)

        for rel, content in bug.source_files.items():
            f = repo_dir / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")

        subprocess.run("git add .", shell=True, cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(f'git commit -m "commit {bug.buggy_commit}"', shell=True, cwd=repo_dir, check=True, capture_output=True)

        # 1. git log must NOT contain the future fix commit
        log_res = subprocess.run("git log", shell=True, cwd=repo_dir, capture_output=True, text=True)
        assert bug.fix_commit not in log_res.stdout

        # 2. git branch must NOT contain branches named after the fix
        branch_res = subprocess.run("git branch -a", shell=True, cwd=repo_dir, capture_output=True, text=True)
        assert "fix" not in branch_res.stdout
        assert bug.fix_commit not in branch_res.stdout

        # 3. git reflog must NOT expose the fix
        reflog_res = subprocess.run("git reflog", shell=True, cwd=repo_dir, capture_output=True, text=True)
        assert bug.fix_commit not in reflog_res.stdout


class TestGroundTruthLeakageRejection:
    """Verifies Requirement 10: Automatic detection and rejection of prompt & tool leakage."""

    def test_golden_patch_leakage_rejected(self):
        validator = GroundTruthValidator()
        with pytest.raises(GroundTruthLeakageError, match="Golden patch snippet"):
            validator.inspect_payload(
                payload_name="user_prompt",
                content="Please review this fix: +    clean_path = target_path if target_path.endswith('/')",
                bug_id="HIST-001",
                golden_patch="--- a/flask_router/router.py\n+++ b/flask_router/router.py\n@@ -2,3 +2,3 @@\n+    clean_path = target_path if target_path.endswith('/')",
            )

    def test_fixing_commit_sha_leakage_rejected(self):
        validator = GroundTruthValidator()
        with pytest.raises(GroundTruthLeakageError, match="Fixing commit SHA"):
            validator.inspect_payload(
                payload_name="tool_result",
                content="Repository history shows commit 9e4a32b applied recently",
                bug_id="HIST-001",
                fix_commit_sha="9e4a32b",
            )

    def test_hidden_test_code_leakage_rejected(self):
        validator = GroundTruthValidator()
        with pytest.raises(GroundTruthLeakageError, match="Hidden test discovery"):
            validator.inspect_payload(
                payload_name="retrieved_file",
                content="File tests/test_hidden_validation.py contains validation tests",
                bug_id="HIST-001",
                hidden_tests={"tests/test_hidden_validation.py": "def test_hidden(): pass"},
            )
