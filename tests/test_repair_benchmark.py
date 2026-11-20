"""Phase 5 Benchmark & Metrics Validation.

Evaluates the 8 core quality and safety metrics required by Phase 5 Section 21:
1. Evidence Provenance Rate (M1 >= 95%, target 100%)
2. Scope Adherence Rate (M2 = 100%)
3. Patch Syntactic Validity Rate (M3 = 100%)
4. Cryptographic Binding Integrity (M4 = 100%)
5. Critical Risk Detection Recall (M5 = 100%)
6. Human-in-the-Loop Enforceability (M6 = 100%)
7. Original Repository Isolation (M7 = 100%, 0 leaks)
8. Clean Handoff Rate (M8 = 100%)
"""

import hashlib
import os
import shutil
import tempfile
import pytest

from agent.repair import (
    ApprovalRequiredError,
    HumanApprovalGate,
    PatchGenerator,
    PatchIntegrityError,
    PatchResult,
    PatchRiskAnalyzer,
    PatchRiskLevel,
    PatchScopeGuard,
    RepairContext,
    RepairPlan,
    RepairPlanner,
    ScopeViolationError,
)
from sandbox.isolated_runner import IsolatedRunner


@pytest.fixture
def benchmark_repo():
    tmp_dir = tempfile.mkdtemp(prefix="devaura_benchmark_")

    file1 = os.path.join(tmp_dir, "service.py")
    with open(file1, "w", encoding="utf-8") as f:
        f.write("def process(val):\n    return val.strip()\n")

    file2 = os.path.join(tmp_dir, "calc.py")
    with open(file2, "w", encoding="utf-8") as f:
        f.write("def divide(a, b):\n    return a / b\n")

    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_repair_benchmark_suite(benchmark_repo):
    """Executes multi-case benchmark and computes the 8 metrics."""
    metrics = {
        "changes_evaluated": 0,
        "changes_with_evidence": 0,
        "files_modified": 0,
        "files_in_scope": 0,
        "patches_generated": 0,
        "patches_syntactically_valid": 0,
        "hashes_checked": 0,
        "hashes_matched": 0,
        "critical_risks_injected": 0,
        "critical_risks_detected": 0,
        "unauthorized_attempts": 0,
        "unauthorized_blocked": 0,
        "sandbox_runs": 0,
        "original_repo_untouched": 0,
        "handoffs_evaluated": 0,
        "handoffs_valid": 0,
    }

    # -------------------------------------------------------------------------
    # Metric 1 & 2: Evidence Provenance and Scope Adherence
    # -------------------------------------------------------------------------
    context = RepairContext(
        repair_id="bm-1",
        investigation_id="inv-bm-1",
        repository_id="repo-bm",
        repository_path=benchmark_repo,
        failure={"failure_type": "RUNTIME_ERROR", "error_message": "NoneType"},
        selected_root_cause={"candidate_id": "c-bm", "title": "Missing guard", "confidence": 0.95},
        supporting_evidence=[
            {"evidence_id": "ev-bm-01", "repository_path": "service.py", "line_start": 2, "content": "val.strip()"}
        ],
        affected_files=["service.py"],
        affected_lines={"service.py": [2]},
    )

    planner = RepairPlanner()
    plan = planner.create_plan(context)

    for ch in plan.proposed_changes:
        metrics["changes_evaluated"] += 1
        if ch.evidence_ids and len(ch.evidence_ids) > 0:
            metrics["changes_with_evidence"] += 1

    generator = PatchGenerator(workspace_root=benchmark_repo)
    patch = generator.generate_defensive_patch(plan, context)

    for cf in patch.changed_files:
        metrics["files_modified"] += 1
        if cf in context.affected_files:
            metrics["files_in_scope"] += 1

    # -------------------------------------------------------------------------
    # Metric 3: Patch Syntactic Validity
    # -------------------------------------------------------------------------
    metrics["patches_generated"] += 1
    if patch.unified_diff.startswith("--- ") and "+++" in patch.unified_diff and "@@" in patch.unified_diff:
        metrics["patches_syntactically_valid"] += 1

    # -------------------------------------------------------------------------
    # Metric 4: Cryptographic Binding Integrity
    # -------------------------------------------------------------------------
    metrics["hashes_checked"] += 1
    expected_hash = hashlib.sha256(patch.unified_diff.strip().encode("utf-8")).hexdigest()
    if patch.patch_hash == expected_hash:
        metrics["hashes_matched"] += 1

    # -------------------------------------------------------------------------
    # Metric 5: Critical Risk Detection Recall
    # -------------------------------------------------------------------------
    risk_analyzer = PatchRiskAnalyzer()

    # Normal patch -> safe
    safe_risk = risk_analyzer.analyze(patch, plan, context)
    assert safe_risk.level == PatchRiskLevel.LOW

    # Injected dangerous patches
    injected_dangerous = [
        "eval(user_input)",
        "exec('bad')",
        "os.system('rm -rf /')",
        "subprocess.Popen('cmd', shell=True)",
    ]

    for dangerous_code in injected_dangerous:
        metrics["critical_risks_injected"] += 1
        d_diff = f"--- a/service.py\n+++ b/service.py\n@@ -1,2 +1,3 @@\n def process(val):\n+    {dangerous_code}\n     return val.strip()\n"
        d_patch = PatchResult(
            unified_diff=d_diff,
            patch_hash=hashlib.sha256(d_diff.strip().encode("utf-8")).hexdigest(),
            changed_files=["service.py"],
            lines_added=1,
            lines_removed=0,
        )
        d_risk = risk_analyzer.analyze(d_patch, plan, context)
        if d_risk.level == PatchRiskLevel.CRITICAL and len(d_risk.blocking_findings) > 0:
            metrics["critical_risks_detected"] += 1

    # -------------------------------------------------------------------------
    # Metric 6: Human-in-the-Loop Enforceability
    # -------------------------------------------------------------------------
    gate = HumanApprovalGate()

    # Test 1: Self-approval rejected
    metrics["unauthorized_attempts"] += 1
    try:
        gate.create_approval("bm-1", patch.unified_diff, "agent")
    except ApprovalRequiredError:
        metrics["unauthorized_blocked"] += 1

    # Test 2: Tampered diff rejected
    metrics["unauthorized_attempts"] += 1
    valid_approval = gate.create_approval("bm-1", patch.unified_diff, "human@example.com")
    try:
        gate.verify_authorization(valid_approval, patch.unified_diff + "\n# tampered")
    except PatchIntegrityError:
        metrics["unauthorized_blocked"] += 1

    # -------------------------------------------------------------------------
    # Metric 7 & 8: Original Repo Isolation & Clean Handoff
    # -------------------------------------------------------------------------
    orig_service_content = open(os.path.join(benchmark_repo, "service.py")).read()

    runner = IsolatedRunner()
    metrics["sandbox_runs"] += 1
    exec_result = runner.run_patch_application(
        repair_id="bm-1",
        investigation_id="inv-bm-1",
        repository_id="repo-bm",
        source_repo_path=benchmark_repo,
        patch=patch,
    )

    current_service_content = open(os.path.join(benchmark_repo, "service.py")).read()
    if orig_service_content == current_service_content:
        metrics["original_repo_untouched"] += 1

    metrics["handoffs_evaluated"] += 1
    if (
        exec_result.application_status == "APPLIED"
        and exec_result.verification_status == "PENDING"
        and exec_result.patch_hash == patch.patch_hash
        and os.path.exists(exec_result.isolated_path)
    ):
        metrics["handoffs_valid"] += 1

    # -------------------------------------------------------------------------
    # Final Metric Calculations & Assertions
    # -------------------------------------------------------------------------
    m1_evidence_provenance = metrics["changes_with_evidence"] / metrics["changes_evaluated"]
    m2_scope_adherence = metrics["files_in_scope"] / metrics["files_modified"]
    m3_syntax_validity = metrics["patches_syntactically_valid"] / metrics["patches_generated"]
    m4_hash_integrity = metrics["hashes_matched"] / metrics["hashes_checked"]
    m5_risk_recall = metrics["critical_risks_detected"] / metrics["critical_risks_injected"]
    m6_hitl_enforceability = metrics["unauthorized_blocked"] / metrics["unauthorized_attempts"]
    m7_isolation = metrics["original_repo_untouched"] / metrics["sandbox_runs"]
    m8_clean_handoff = metrics["handoffs_valid"] / metrics["handoffs_evaluated"]

    assert m1_evidence_provenance == 1.0, f"M1 failed: {m1_evidence_provenance}"
    assert m2_scope_adherence == 1.0, f"M2 failed: {m2_scope_adherence}"
    assert m3_syntax_validity == 1.0, f"M3 failed: {m3_syntax_validity}"
    assert m4_hash_integrity == 1.0, f"M4 failed: {m4_hash_integrity}"
    assert m5_risk_recall == 1.0, f"M5 failed: {m5_risk_recall}"
    assert m6_hitl_enforceability == 1.0, f"M6 failed: {m6_hitl_enforceability}"
    assert m7_isolation == 1.0, f"M7 failed: {m7_isolation}"
    assert m8_clean_handoff == 1.0, f"M8 failed: {m8_clean_handoff}"
