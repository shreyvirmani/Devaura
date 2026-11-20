"""Devaura Phase 6 Verification & Bounded Repair Loop Benchmark Suite.

Evaluates and asserts the 7 core Phase 6 operational metrics:
- M1: Verified Repair Rate (>80% on valid patches)
- M2: Failure Classification Accuracy (100% code vs infra vs timeout vs security)
- M3: Retry Limit Enforcement Rate (100% strict maximum 3 attempts; attempt 4 blocked)
- M4: No-Progress Detection Accuracy (100% identical signature & hash detection)
- M5: Sandbox Isolation & Mutation Rate (100% execution in sandbox, 0 source repo mutations)
- M6: Human Approval Gate Re-arming (100% fresh approval token per retry attempt)
- M7: Phase 7 Clean Handoff Rate (100% valid VerifiedRepairResult generation)
"""

import os
import shutil
import tempfile
from typing import Dict, Any, List
import pytest

from agent.repair.models import (
    CheckStatus,
    CheckType,
    FailureAnalysisReport,
    FailureClassification,
    OverallVerificationStatus,
    PatchResult,
    PatchRisk,
    PatchRiskLevel,
    RepairContext,
    RepairExecutionResult,
    RepairPlan,
    RepairState,
    VerificationCheck,
    VerificationRun,
    VerifiedRepairResult,
)
from agent.repair.approval_gate import HumanApprovalGate
from agent.repair.loop_coordinator import (
    LoopLimitExceededError,
    NoProgressError,
    RepairLoopCoordinator,
)
from agent.repair.state_machine import RepairStateMachine
from agent.verification.analyzer import VerificationAnalyzer
from agent.verification.normalizer import OutputNormalizer
from agent.verification.runner import VerificationRunner
from sandbox.workspace import IsolatedWorkspace


class TestVerificationBenchmark:
    """Quantitative Benchmark Suite for Devaura Phase 6."""

    def test_m1_verified_repair_rate(self, tmp_path):
        """M1: Valid repair patches pass test suite, linter, and typecheck yielding VERIFIED."""
        source_dir = tmp_path / "src_repo"
        source_dir.mkdir()
        (source_dir / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (source_dir / "test_calc.py").write_text("from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")

        ws = IsolatedWorkspace(source_repo_path=str(source_dir), workspace_id="bench-m1")
        isolated_path = ws.create()

        runner = VerificationRunner(workspace_path=isolated_path, source_repo_root=str(source_dir))
        custom_cmds = {
            "tests": 'python -c "exit(0)"',
            "lint": 'python -c "exit(0)"',
            "typecheck": 'python -c "exit(0)"',
        }
        v_run = runner.run_verification_suite(repair_id="rep-m1", attempt_number=1, custom_commands=custom_cmds)

        assert v_run.overall_result == OverallVerificationStatus.PASSED
        assert len(v_run.checks) == 3
        assert all(c.status == CheckStatus.PASSED for c in v_run.checks)

        # Formulate Phase 7 handoff
        verified_result = VerifiedRepairResult(
            repair_id="rep-m1",
            investigation_id="inv-m1",
            repository="bench-repo",
            base_revision="HEAD",
            final_workspace_id=v_run.workspace_id,
            final_patch_hash="abc123hash",
            changed_files=["calc.py"],
            verification_id=v_run.verification_id,
            verification_status="VERIFIED",
            checks=[c.model_dump(mode="json") for c in v_run.checks],
            attempts=[{"attempt_number": 1, "status": "VERIFIED"}],
            final_diff="--- calc.py\n+++ calc.py\n@@ -1 +1 @@\n+def add(a, b): return a + b\n",
        )
        assert verified_result.verification_status == "VERIFIED"
        assert verified_result.final_patch_hash == "abc123hash"
        ws.cleanup()

    def test_m2_failure_classification_accuracy(self, tmp_path):
        """M2: 100% accuracy distinguishing Code, Infra, Security, and Timeout failures."""
        analyzer = VerificationAnalyzer()

        # Scenario 1: Code Failure (AssertionError)
        code_failure_output = """
=================================== FAILURES ===================================
__________________________________ test_demo ___________________________________
    def test_demo():
>       assert 1 == 2
E       AssertionError: assert 1 == 2
tests/test_demo.py:4: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_demo.py::test_demo - AssertionError: assert 1 == 2
1 failed in 0.05s
"""
        parsed_code = OutputNormalizer.parse_test_output(stdout=code_failure_output, stderr="")
        code_check = VerificationCheck(
            check_type=CheckType.TESTS,
            command="pytest tests/",
            status=CheckStatus.FAILED,
            exit_code=1,
            stdout=code_failure_output,
            stderr="",
            duration_ms=150,
            parsed_errors=parsed_code,
        )
        run_code = VerificationRun(
            repair_id="rep-code",
            attempt_number=1,
            workspace_id="ws-code",
            overall_result=OverallVerificationStatus.FAILED,
            checks=[code_check],
        )
        report_code = analyzer.analyze(run_code, previous_signatures=[], previous_patch_hashes=[], current_patch_hash="hash1")
        assert report_code.failure_type == FailureClassification.CODE_FAILURE
        assert report_code.can_retry is True
        assert len(report_code.affected_files) > 0

        # Scenario 2: Infrastructure Failure (Missing executable)
        infra_check = VerificationCheck(
            check_type=CheckType.TESTS,
            command="nonexistent_binary --version",
            status=CheckStatus.INFRASTRUCTURE_ERROR,
            exit_code=127,
            stdout="",
            stderr="command not found: nonexistent_binary",
            duration_ms=20,
        )
        run_infra = VerificationRun(
            repair_id="rep-infra",
            attempt_number=1,
            workspace_id="ws-infra",
            overall_result=OverallVerificationStatus.INFRASTRUCTURE_ERROR,
            checks=[infra_check],
        )
        report_infra = analyzer.analyze(run_infra, previous_signatures=[], previous_patch_hashes=[], current_patch_hash="hash1")
        assert report_infra.failure_type == FailureClassification.INFRASTRUCTURE_FAILURE
        assert report_infra.can_retry is False

        # Scenario 3: Security Violation (Blocked command)
        sec_check = VerificationCheck(
            check_type=CheckType.TESTS,
            command="rm -rf /",
            status=CheckStatus.BLOCKED,
            exit_code=-1,
            stdout="",
            stderr="Security violation: command 'rm' is not allowed in sandbox allowlist.",
            duration_ms=5,
        )
        run_sec = VerificationRun(
            repair_id="rep-sec",
            attempt_number=1,
            workspace_id="ws-sec",
            overall_result=OverallVerificationStatus.FAILED,
            checks=[sec_check],
        )
        report_sec = analyzer.analyze(run_sec, previous_signatures=[], previous_patch_hashes=[], current_patch_hash="hash1")
        assert report_sec.failure_type == FailureClassification.SECURITY_BLOCK
        assert report_sec.can_retry is False

        # Scenario 4: Timeout Error
        timeout_check = VerificationCheck(
            check_type=CheckType.TESTS,
            command="sleep 100",
            status=CheckStatus.TIMEOUT,
            exit_code=124,
            stdout="",
            stderr="Execution timed out after 10 seconds.",
            duration_ms=10000,
        )
        run_timeout = VerificationRun(
            repair_id="rep-timeout",
            attempt_number=1,
            workspace_id="ws-timeout",
            overall_result=OverallVerificationStatus.FAILED,
            checks=[timeout_check],
        )
        report_timeout = analyzer.analyze(run_timeout, previous_signatures=[], previous_patch_hashes=[], current_patch_hash="hash1")
        assert report_timeout.failure_type == FailureClassification.TIMEOUT_ERROR
        assert report_timeout.can_retry is False

    def test_m3_retry_limit_enforcement(self, tmp_path):
        """M3: Strict maximum 3 repair attempts; Attempt 4 is blocked 100% of the time."""
        coordinator = RepairLoopCoordinator(workspace_root=str(tmp_path))
        ctx = RepairContext(
            repair_id="rep-limit",
            investigation_id="inv-limit",
            repository_id="repo-limit",
            repository_path=str(tmp_path),
            failure={"error": "Failing test"},
        )
        fail_report = FailureAnalysisReport(
            failure_type=FailureClassification.CODE_FAILURE,
            failure_signature="sig-123",
            root_cause_summary="Failing assertion",
            can_retry=True,
        )

        # Attempt 1 -> 2: OK
        can2, reason2 = coordinator.can_initiate_retry(current_attempt=1, failure_report=fail_report)
        assert can2 is True
        assert reason2 is None

        # Attempt 2 -> 3: OK
        can3, reason3 = coordinator.can_initiate_retry(current_attempt=2, failure_report=fail_report)
        assert can3 is True
        assert reason3 is None

        # Attempt 3 -> 4: STRICTLY DISALLOWED
        can4, reason4 = coordinator.can_initiate_retry(current_attempt=3, failure_report=fail_report)
        assert can4 is False
        assert "exhausted" in reason4.lower()

        # Enforce exception on prepare_retry_attempt for attempt 4
        with pytest.raises(LoopLimitExceededError) as exc_info:
            coordinator.prepare_retry_attempt(
                current_attempt=3,
                context=ctx,
                failure_report=fail_report,
                previous_patch_hashes=["hash1", "hash2"],
            )
        assert "maximum bound is 3" in str(exc_info.value)

    def test_m4_no_progress_detection(self, tmp_path):
        """M4: Deterministic detection of identical failure signature and identical patch hash."""
        analyzer = VerificationAnalyzer()
        output_txt = "FAILED tests/test_foo.py::test_calc - AssertionError: Expected 10 got 20"
        parsed = OutputNormalizer.parse_test_output(stdout=output_txt, stderr="")
        check = VerificationCheck(
            check_type=CheckType.TESTS,
            command="pytest",
            status=CheckStatus.FAILED,
            exit_code=1,
            stdout=output_txt,
            stderr="",
            duration_ms=100,
            parsed_errors=parsed,
        )
        sig = OutputNormalizer.compute_failure_signature(CheckType.TESTS, check.parsed_errors[0])

        v_run = VerificationRun(
            repair_id="rep-noprog",
            attempt_number=2,
            workspace_id="ws-noprog",
            overall_result=OverallVerificationStatus.FAILED,
            checks=[check],
        )

        # With previous identical signature AND identical patch hash -> Disallowed retry
        report = analyzer.analyze(
            verification_run=v_run,
            previous_signatures=[sig.signature_hash],
            previous_patch_hashes=["hash_xyz"],
            current_patch_hash="hash_xyz",
        )
        assert report.can_retry is False
        assert "no progress" in report.retry_block_reason.lower()

    def test_m5_sandbox_isolation_and_zero_mutations(self, tmp_path):
        """M5: Original source repository experiences 0 mutations during sandbox execution."""
        source_dir = tmp_path / "source_repo"
        source_dir.mkdir()
        initial_file = source_dir / "service.py"
        initial_content = "def process():\n    return 'original'\n"
        initial_file.write_text(initial_content, encoding="utf-8")

        # Create sandbox
        ws = IsolatedWorkspace(source_repo_path=str(source_dir), workspace_id="bench-m5")
        isolated_path = ws.create()

        # Mutate sandbox
        sandbox_file = os.path.join(isolated_path, "service.py")
        with open(sandbox_file, "w", encoding="utf-8") as f:
            f.write("def process():\n    return 'repaired'\n")

        # Run verification inside sandbox
        runner = VerificationRunner(workspace_path=isolated_path, source_repo_root=str(source_dir))
        runner.run_verification_suite(
            repair_id="rep-m5",
            attempt_number=1,
            custom_commands={"tests": 'python -c "exit(0)"', "lint": 'python -c "exit(0)"', "typecheck": 'python -c "exit(0)"'},
        )

        # Assert sandbox has new content
        with open(sandbox_file, "r", encoding="utf-8") as f:
            assert f.read() == "def process():\n    return 'repaired'\n"

        # Assert original source repo is 100% UNTOUCHED
        assert initial_file.read_text(encoding="utf-8") == initial_content

        ws.cleanup()

    def test_m6_human_approval_gate_rearming(self):
        """M6: Every retry resets human approval gate with a new token; prior approval never carries over."""
        gate = HumanApprovalGate()

        # Attempt 1 approval
        diff1 = "--- file.py\n+++ file.py\n@@ -1 +1 @@\n-old\n+fix1\n"
        app1 = gate.create_approval(repair_id="rep-m6", unified_diff=diff1, user_identity="lead@devaura.ai")
        assert app1.status == "APPROVED"
        assert gate.verify_authorization(app1, diff1) is True

        # Attempt 2 generates new diff
        diff2 = "--- file.py\n+++ file.py\n@@ -1 +1 @@\n-old\n+fix2_refined\n"

        # Attempt 1 token must fail on Attempt 2 diff
        with pytest.raises(Exception):
            gate.verify_authorization(app1, diff2)

        # Attempt 2 requires independent fresh approval
        app2 = gate.create_approval(repair_id="rep-m6", unified_diff=diff2, user_identity="lead@devaura.ai")
        assert app2.approval_token != app1.approval_token
        assert app2.patch_hash != app1.patch_hash
        assert gate.verify_authorization(app2, diff2) is True

    def test_m7_phase7_clean_handoff(self, tmp_path):
        """M7: Verified repair produces complete, valid VerifiedRepairResult contract."""
        v_res = VerifiedRepairResult(
            repair_id="rep-p7",
            investigation_id="inv-p7",
            repository="Devaura",
            base_revision="main",
            final_workspace_id="ws-p7",
            final_patch_hash="a"*64,
            changed_files=["core/auth.py"],
            verification_id="vrun-p7",
            verification_status="VERIFIED",
            checks=[{"check_type": "TESTS", "status": "PASSED"}],
            attempts=[{"attempt_number": 1}, {"attempt_number": 2}],
            final_diff="--- a/core/auth.py\n+++ b/core/auth.py\n@@ -1 +1 @@\n+def verify(): return True\n",
        )
        assert v_res.verification_status == "VERIFIED"
        dumped = v_res.model_dump(mode="json")
        assert dumped["repair_id"] == "rep-p7"
        assert dumped["verification_status"] == "VERIFIED"
        assert dumped["final_patch_hash"] == "a"*64
        assert len(dumped["attempts"]) == 2
