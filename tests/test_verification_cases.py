"""Devaura Phase 6 Deterministic Verification & Bounded Loop Test Cases.

Validates the 12 core verification scenarios specified in Phase 6 Section 25:
Case 1: Passing repair -> VERIFIED
Case 2: Test failure -> VERIFICATION_FAILED
Case 3: Lint failure -> FAILED
Case 4: Typecheck failure -> FAILED
Case 5: Infrastructure failure (missing binary) -> INFRASTRUCTURE_FAILURE, no retry
Case 6: Timeout -> TIMEOUT, no blind retry
Case 7: Successful retry (Attempt 1 fail, Attempt 2 verified)
Case 8: Three failed attempts -> REPAIR_EXHAUSTED (Attempt 4 blocked)
Case 9: Identical retry -> NO_PROGRESS
Case 10: Approval bypass on retry -> Denied
Case 11: Original repository isolation -> 0 mutations
Case 12: Patch hash integrity -> PATCH_CHANGED
"""

import os
import shutil
import tempfile
import uuid
import pytest

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
from agent.repair.models import (
    ApprovalStatus,
    CheckStatus,
    CheckType,
    FailureAnalysisReport,
    FailureClassification,
    OverallVerificationStatus,
    PatchResult,
    ProposedChange,
    RepairApproval,
    RepairContext,
    RepairPlan,
    RepairState,
    VerificationCheck,
    VerificationRun,
    VerifiedRepairResult,
)
from agent.repair.patch_generator import PatchGenerator
from agent.repair.planner import RepairPlanner
from agent.repair.state_machine import (
    InvalidRepairStateTransitionError,
    RepairStateMachine,
)
from agent.verification.analyzer import VerificationAnalyzer
from agent.verification.normalizer import OutputNormalizer
from agent.verification.runner import VerificationRunner, VerificationSecurityError
from sandbox.isolated_runner import IsolatedRunner


@pytest.fixture
def temp_workspace():
    """Create a temporary sandbox workspace fixture."""
    tmp_dir = tempfile.mkdtemp(prefix="devaura_test_ws_")

    # Create dummy source and test files
    pkg_dir = os.path.join(tmp_dir, "pkg")
    os.makedirs(pkg_dir, exist_ok=True)

    calc_file = os.path.join(pkg_dir, "calc.py")
    with open(calc_file, "w", encoding="utf-8") as f:
        f.write("def divide(a, b):\n    if b == 0:\n        return None\n    return a / b\n")

    test_file = os.path.join(tmp_dir, "test_calc.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(
            "import pytest\n"
            "from pkg.calc import divide\n\n"
            "def test_divide_valid():\n    assert divide(4, 2) == 2\n\n"
            "def test_divide_zero():\n    assert divide(4, 0) is None\n"
        )

    # Helper scripts without semicolons for deterministic testing
    fail_test = os.path.join(tmp_dir, "fail_test.py")
    with open(fail_test, "w", encoding="utf-8") as f:
        f.write(
            "import sys\n"
            "sys.stderr.write('FAILED test_calc.py::test_divide - AssertionError: expected 2 got 3\\n')\n"
            "sys.exit(1)\n"
        )

    fail_lint = os.path.join(tmp_dir, "fail_lint.py")
    with open(fail_lint, "w", encoding="utf-8") as f:
        f.write(
            "import sys\n"
            "sys.stderr.write('pkg/calc.py:2:1: E302 expected 2 blank lines\\n')\n"
            "sys.exit(1)\n"
        )

    fail_type = os.path.join(tmp_dir, "fail_type.py")
    with open(fail_type, "w", encoding="utf-8") as f:
        f.write(
            "import sys\n"
            "sys.stderr.write('pkg/calc.py:4: error: Incompatible return value type (got None, expected int)\\n')\n"
            "sys.exit(1)\n"
        )

    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def temp_source_repo():
    """Create a temporary source repository fixture."""
    tmp_dir = tempfile.mkdtemp(prefix="devaura_test_source_")
    file_path = os.path.join(tmp_dir, "app.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# Untouched source repo\ndef main(): pass\n")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# Case 1: Passing repair -> VERIFIED
# -----------------------------------------------------------------------------
def test_case_1_passing_repair(temp_workspace, temp_source_repo):
    runner = VerificationRunner(
        workspace_path=temp_workspace,
        source_repo_root=temp_source_repo,
    )

    custom_cmds = {
        "tests": 'python -c "exit(0)"',
        "lint": 'python -c "exit(0)"',
        "typecheck": 'python -c "exit(0)"',
    }

    run = runner.run_verification_suite(
        repair_id="rep-c1",
        attempt_number=1,
        custom_commands=custom_cmds,
    )

    assert run.overall_result == "PASSED"
    assert run.status == OverallVerificationStatus.PASSED
    assert len(run.checks) == 3
    assert all(c.status == CheckStatus.PASSED for c in run.checks)

    sm = RepairStateMachine(RepairState.PATCH_APPLIED_PENDING_VERIFICATION)
    sm.transition(RepairState.VERIFYING)
    sm.transition(RepairState.VERIFIED)
    assert sm.current_state == RepairState.VERIFIED


# -----------------------------------------------------------------------------
# Case 2: Test failure -> VERIFICATION_FAILED
# -----------------------------------------------------------------------------
def test_case_2_test_failure(temp_workspace, temp_source_repo):
    runner = VerificationRunner(
        workspace_path=temp_workspace,
        source_repo_root=temp_source_repo,
    )

    custom_cmds = {
        "tests": "python fail_test.py",
        "lint": 'python -c "exit(0)"',
        "typecheck": 'python -c "exit(0)"',
    }

    run = runner.run_verification_suite(
        repair_id="rep-c2",
        attempt_number=1,
        custom_commands=custom_cmds,
    )

    assert run.overall_result == "FAILED"
    test_chk = next(c for c in run.checks if c.check_type == CheckType.TESTS)
    assert test_chk.status == CheckStatus.FAILED
    assert test_chk.exit_code == 1

    # Analyzer diagnosis
    analyzer = VerificationAnalyzer()
    analysis = analyzer.analyze(run)
    assert analysis.failure_type == FailureClassification.CODE_FAILURE
    assert analysis.can_retry is True
    assert analysis.failure_signature is not None

    sm = RepairStateMachine(RepairState.PATCH_APPLIED_PENDING_VERIFICATION)
    sm.transition(RepairState.VERIFYING)
    sm.transition(RepairState.VERIFICATION_FAILED)
    sm.transition(RepairState.ANALYZING_FAILURE)
    sm.transition(RepairState.REPAIR_RETRY_ELIGIBLE)
    assert sm.current_state == RepairState.REPAIR_RETRY_ELIGIBLE


# -----------------------------------------------------------------------------
# Case 3: Lint failure -> FAILED
# -----------------------------------------------------------------------------
def test_case_3_lint_failure(temp_workspace, temp_source_repo):
    runner = VerificationRunner(
        workspace_path=temp_workspace,
        source_repo_root=temp_source_repo,
    )

    custom_cmds = {
        "tests": 'python -c "exit(0)"',
        "lint": "python fail_lint.py",
        "typecheck": 'python -c "exit(0)"',
    }

    run = runner.run_verification_suite(
        repair_id="rep-c3",
        attempt_number=1,
        custom_commands=custom_cmds,
    )

    assert run.overall_result == "FAILED"
    lint_chk = next(c for c in run.checks if c.check_type == CheckType.LINT)
    assert lint_chk.status == CheckStatus.FAILED
    assert len(lint_chk.parsed_errors) > 0
    assert lint_chk.parsed_errors[0].file == "pkg/calc.py"


# -----------------------------------------------------------------------------
# Case 4: Typecheck failure -> FAILED
# -----------------------------------------------------------------------------
def test_case_4_typecheck_failure(temp_workspace, temp_source_repo):
    runner = VerificationRunner(
        workspace_path=temp_workspace,
        source_repo_root=temp_source_repo,
    )

    custom_cmds = {
        "tests": 'python -c "exit(0)"',
        "lint": 'python -c "exit(0)"',
        "typecheck": "python fail_type.py",
    }

    run = runner.run_verification_suite(
        repair_id="rep-c4",
        attempt_number=1,
        custom_commands=custom_cmds,
    )

    assert run.overall_result == "FAILED"
    tc_chk = next(c for c in run.checks if c.check_type == CheckType.TYPECHECK)
    assert tc_chk.status == CheckStatus.FAILED
    assert len(tc_chk.parsed_errors) > 0
    assert "Incompatible return value type" in tc_chk.parsed_errors[0].message


# -----------------------------------------------------------------------------
# Case 5: Infrastructure failure (missing binary) -> INFRASTRUCTURE_FAILURE, no retry
# -----------------------------------------------------------------------------
def test_case_5_infrastructure_failure(temp_workspace, temp_source_repo):
    runner = VerificationRunner(
        workspace_path=temp_workspace,
        source_repo_root=temp_source_repo,
    )

    run = VerificationRun(
        verification_id="v-infra",
        repair_id="rep-infra",
        attempt_number=1,
        workspace_id="ws-1",
        checks=[
            VerificationCheck(
                check_type=CheckType.TESTS,
                command="pytest -q",
                status=CheckStatus.INFRASTRUCTURE_ERROR,
                exit_code=127,
                stderr="Executable missing: /usr/bin/pytest",
            )
        ],
        overall_result="INFRASTRUCTURE_ERROR",
    )

    analyzer = VerificationAnalyzer()
    analysis = analyzer.analyze(run)
    assert analysis.failure_type == FailureClassification.INFRASTRUCTURE_FAILURE
    assert analysis.can_retry is False
    assert "Infrastructure" in analysis.retry_block_reason

    sm = RepairStateMachine(RepairState.ANALYZING_FAILURE)
    sm.transition(RepairState.INFRASTRUCTURE_FAILURE)
    assert sm.current_state == RepairState.INFRASTRUCTURE_FAILURE


# -----------------------------------------------------------------------------
# Case 6: Timeout -> TIMEOUT, no blind retry
# -----------------------------------------------------------------------------
def test_case_6_timeout_no_blind_retry(temp_workspace, temp_source_repo):
    sleep_script = os.path.join(temp_workspace, "sleep.py")
    with open(sleep_script, "w", encoding="utf-8") as f:
        f.write("import time\ntime.sleep(2)\n")

    runner = VerificationRunner(
        workspace_path=temp_workspace,
        source_repo_root=temp_source_repo,
    )

    check = runner.run_check(CheckType.TESTS, "python sleep.py", timeout_seconds=1)

    assert check.status == CheckStatus.TIMEOUT
    assert check.exit_code == 124
    assert "timed out" in check.stderr

    run = VerificationRun(
        verification_id="v-timeout",
        repair_id="rep-timeout",
        attempt_number=1,
        workspace_id="ws-1",
        checks=[check],
        overall_result="TIMEOUT",
    )

    analyzer = VerificationAnalyzer()
    analysis = analyzer.analyze(run)
    assert analysis.failure_type == FailureClassification.TIMEOUT_ERROR
    assert analysis.can_retry is False


# -----------------------------------------------------------------------------
# Case 7: Successful retry (Attempt 1 fail, Attempt 2 verified)
# -----------------------------------------------------------------------------
def test_case_7_successful_retry(temp_workspace):
    coordinator = RepairLoopCoordinator(workspace_root=temp_workspace)

    context = RepairContext(
        repair_id="rep-c7",
        investigation_id="inv-c7",
        repository_id="repo-c7",
        repository_path=temp_workspace,
        failure={"error_message": "IndexError: list index out of range"},
        affected_files=["pkg/calc.py"],
    )

    failure_report = FailureAnalysisReport(
        failure_type=FailureClassification.CODE_FAILURE,
        failure_signature="sig_hash_attempt1",
        root_cause_summary="Assertion failed on division edge cases",
        can_retry=True,
    )

    # 1. Attempt 1 has initial patch
    plan1 = RepairPlan(
        repair_id="rep-c7",
        investigation_id="inv-c7",
        objective="Initial patch",
        root_cause="Missing null check",
        proposed_changes=[
            ProposedChange(
                file="pkg/calc.py",
                location="line 2",
                rationale="add guard",
                expected_effect="prevents zero division",
            )
        ],
    )
    generator = PatchGenerator(workspace_root=temp_workspace)
    patch1 = generator.generate_from_content_map(
        plan=plan1,
        context=context,
        modified_contents={"pkg/calc.py": "def divide(a, b):\n    # v1\n    return a / b\n"},
    )

    # 2. Prepare Attempt 2
    plan2, patch2, risk2 = coordinator.prepare_retry_attempt(
        current_attempt=1,
        context=context,
        failure_report=failure_report,
        previous_patch_hashes=[patch1.patch_hash],
        custom_modified_contents={"pkg/calc.py": "def divide(a, b):\n    # v2 fixed\n    if b == 0: return 0\n    return a / b\n"},
    )

    assert patch2.patch_hash != patch1.patch_hash
    assert risk2.level.value in {"LOW", "MEDIUM"}

    # Attempt 2 verification succeeds
    runner = VerificationRunner(workspace_path=temp_workspace)
    run2 = runner.run_verification_suite(
        repair_id="rep-c7",
        attempt_number=2,
        custom_commands={
            "tests": 'python -c "exit(0)"',
            "lint": 'python -c "exit(0)"',
            "typecheck": 'python -c "exit(0)"',
        },
    )
    assert run2.overall_result == "PASSED"

    # Phase 7 handoff contract
    verified_result = VerifiedRepairResult(
        repair_id="rep-c7",
        investigation_id="inv-c7",
        repository="repo-c7",
        base_revision="HEAD",
        final_workspace_id=run2.workspace_id,
        final_patch_hash=patch2.patch_hash,
        changed_files=["pkg/calc.py"],
        verification_id=run2.verification_id,
        verification_status="VERIFIED",
        final_diff=patch2.unified_diff,
    )
    assert verified_result.verification_status == "VERIFIED"


# -----------------------------------------------------------------------------
# Case 8: Three failed attempts -> REPAIR_EXHAUSTED (Attempt 4 blocked)
# -----------------------------------------------------------------------------
def test_case_8_three_failed_attempts_exhaustion(temp_workspace):
    coordinator = RepairLoopCoordinator(workspace_root=temp_workspace)
    context = RepairContext(
        repair_id="rep-c8",
        investigation_id="inv-c8",
        repository_id="repo-c8",
        repository_path=temp_workspace,
        failure={"error_message": "Regression"},
        affected_files=["pkg/calc.py"],
    )

    failure_report = FailureAnalysisReport(
        failure_type=FailureClassification.CODE_FAILURE,
        failure_signature="sig-fail",
        root_cause_summary="Still failing",
        can_retry=True,
    )

    # Attempt 1 -> Attempt 2 allowed
    can_retry_1, _ = coordinator.can_initiate_retry(1, failure_report)
    assert can_retry_1 is True

    # Attempt 2 -> Attempt 3 allowed
    can_retry_2, _ = coordinator.can_initiate_retry(2, failure_report)
    assert can_retry_2 is True

    # Attempt 3 -> Attempt 4 MUST BE BLOCKED
    can_retry_3, reason_3 = coordinator.can_initiate_retry(3, failure_report)
    assert can_retry_3 is False
    assert "exhausted" in reason_3

    with pytest.raises(LoopLimitExceededError):
        coordinator.prepare_retry_attempt(
            current_attempt=3,
            context=context,
            failure_report=failure_report,
            previous_patch_hashes=["hash1", "hash2", "hash3"],
        )

    # State machine transition to REPAIR_EXHAUSTED
    sm = RepairStateMachine(RepairState.ANALYZING_FAILURE)
    sm.transition(RepairState.REPAIR_EXHAUSTED)
    assert sm.current_state == RepairState.REPAIR_EXHAUSTED

    # From REPAIR_EXHAUSTED, no further planning or retries are permitted
    with pytest.raises(InvalidRepairStateTransitionError):
        sm.transition(RepairState.PLANNING)


# -----------------------------------------------------------------------------
# Case 9: Identical retry -> NO_PROGRESS
# -----------------------------------------------------------------------------
def test_case_9_identical_retry_no_progress(temp_workspace):
    coordinator = RepairLoopCoordinator(workspace_root=temp_workspace)
    context = RepairContext(
        repair_id="rep-c9",
        investigation_id="inv-c9",
        repository_id="repo-c9",
        repository_path=temp_workspace,
        failure={"error_message": "SyntaxError"},
        affected_files=["pkg/calc.py"],
    )

    generator = PatchGenerator(workspace_root=temp_workspace)
    plan = RepairPlan(
        repair_id="rep-c9",
        investigation_id="inv-c9",
        objective="Fix",
        root_cause="Bug",
        proposed_changes=[
            ProposedChange(
                file="pkg/calc.py",
                location="1",
                rationale="test",
                expected_effect="prevents syntax error",
            )
        ],
    )
    patch = generator.generate_from_content_map(
        plan=plan,
        context=context,
        modified_contents={"pkg/calc.py": "# identical\ndef divide(): pass\n"},
    )

    failure_report = FailureAnalysisReport(
        failure_type=FailureClassification.CODE_FAILURE,
        failure_signature="sig-same",
        root_cause_summary="Still broken",
        can_retry=True,
    )

    # Providing the exact same patch hash triggers NoProgressError
    with pytest.raises(NoProgressError):
        coordinator.prepare_retry_attempt(
            current_attempt=1,
            context=context,
            failure_report=failure_report,
            previous_patch_hashes=[patch.patch_hash],
            custom_modified_contents={"pkg/calc.py": "# identical\ndef divide(): pass\n"},
        )

    sm = RepairStateMachine(RepairState.ANALYZING_FAILURE)
    sm.transition(RepairState.NO_PROGRESS)
    assert sm.current_state == RepairState.NO_PROGRESS


# -----------------------------------------------------------------------------
# Case 10: Approval bypass on retry -> Denied
# -----------------------------------------------------------------------------
def test_case_10_approval_bypass_on_retry(temp_workspace):
    gate = HumanApprovalGate()

    patch1_diff = "--- a/pkg/calc.py\n+++ b/pkg/calc.py\n@@ -1 +1 @@\n-old\n+new1\n"
    patch2_diff = "--- a/pkg/calc.py\n+++ b/pkg/calc.py\n@@ -1 +1 @@\n-old\n+new2_retry\n"

    # Human approved Attempt 1
    approval_1 = gate.create_approval(
        repair_id="rep-c10",
        unified_diff=patch1_diff,
        user_identity="reviewer@devaura.ai",
    )
    assert approval_1.status == ApprovalStatus.APPROVED

    # Attempting to use Attempt 1 approval on Attempt 2 patch diff MUST FAIL
    with pytest.raises(PatchIntegrityError):
        gate.verify_authorization(approval_1, patch2_diff)

    # Attempting to apply Attempt 2 with PENDING status MUST FAIL
    approval_2_pending = RepairApproval(
        repair_id="rep-c10",
        patch_hash=HumanApprovalGate.compute_patch_hash(patch2_diff),
        approved_by="pending",
        approval_token=str(uuid.uuid4()),
        status=ApprovalStatus.PENDING,
    )
    with pytest.raises(ApprovalRequiredError):
        gate.verify_authorization(approval_2_pending, patch2_diff)


# -----------------------------------------------------------------------------
# Case 11: Original repository isolation -> 0 mutations
# -----------------------------------------------------------------------------
def test_case_11_original_repo_isolation(temp_source_repo):
    file_path = os.path.join(temp_source_repo, "app.py")
    with open(file_path, "r", encoding="utf-8") as f:
        original_content = f.read()

    runner = IsolatedRunner()
    patch = PatchResult(
        status="GENERATED",
        unified_diff="--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,3 @@\n # Untouched source repo\n+# Mutated in sandbox\n def main(): pass\n",
        patch_hash="patch_hash_11",
        changed_files=["app.py"],
        lines_added=1,
        lines_removed=0,
    )

    exec_result = runner.run_patch_application(
        repair_id="rep-c11",
        investigation_id="inv-c11",
        repository_id="repo-c11",
        source_repo_path=temp_source_repo,
        patch=patch,
    )

    # Verify sandbox is mutated
    sandbox_file = os.path.join(exec_result.isolated_path, "app.py")
    with open(sandbox_file, "r", encoding="utf-8") as f:
        sandbox_content = f.read()
    assert "# Mutated in sandbox" in sandbox_content

    # Verify original repository is completely untouched (0 mutations)
    with open(file_path, "r", encoding="utf-8") as f:
        current_source_content = f.read()
    assert current_source_content == original_content

    # Verify VerificationRunner rejects executing on original repository
    v_runner = VerificationRunner(
        workspace_path=temp_source_repo,
        source_repo_root=temp_source_repo,
    )
    with pytest.raises(VerificationSecurityError):
        v_runner.validate_sandbox_isolation()


# -----------------------------------------------------------------------------
# Case 12: Patch hash integrity -> PATCH_CHANGED
# -----------------------------------------------------------------------------
def test_case_12_patch_hash_tampering():
    gate = HumanApprovalGate()
    original_diff = "--- a/pkg/calc.py\n+++ b/pkg/calc.py\n@@ -1 +1 @@\n-a\n+b\n"
    approval = gate.create_approval(
        repair_id="rep-c12",
        unified_diff=original_diff,
        user_identity="lead@devaura.ai",
    )

    tampered_diff = "--- a/pkg/calc.py\n+++ b/pkg/calc.py\n@@ -1 +1 @@\n-a\n+tampered_malicious_code()\n"

    with pytest.raises(PatchIntegrityError) as exc_info:
        gate.verify_authorization(approval, tampered_diff)
    assert "mismatch" in str(exc_info.value).lower()

    # State machine transition to PATCH_CHANGED
    sm = RepairStateMachine(RepairState.APPLYING)
    sm.transition(RepairState.PATCH_CHANGED)
    assert sm.current_state == RepairState.PATCH_CHANGED
