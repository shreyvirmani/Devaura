"""Devaura Phase 5 Deterministic Repair Test Cases.

Validates the 10 core repair scenarios specified in Phase 5 Section 20:
Case 1: Single-file logic bug (minimal patch, applied in sandbox)
Case 2: Null/None guard addition
Case 3: Unhandled exception / KeyError defensive check
Case 4: Multi-file coordinated repair bounded to evidence
Case 5: Out-of-scope file modification rejection
Case 6: Path traversal rejection
Case 7: Sensitive file modification rejection
Case 8: Dangerous execution / secret leakage detected by risk analyzer
Case 9: Cryptographic patch tampering detected by approval gate
Case 10: Insufficient investigation evidence blocks repair lifecycle
"""

import hashlib
import os
import shutil
import tempfile
import pytest

from agent.models import EvidenceSufficiency
from agent.repair import (
    ApprovalRequiredError,
    HumanApprovalGate,
    InvalidRepairStateTransitionError,
    PatchGenerator,
    PatchIntegrityError,
    PatchResult,
    PatchRiskAnalyzer,
    PatchRiskLevel,
    PatchScopeGuard,
    RepairContext,
    RepairContextBuilder,
    RepairPlan,
    RepairPlanner,
    RepairStateMachine,
    RepairState,
    ScopeViolationError,
)
from sandbox.isolated_runner import IsolatedRunner
from sandbox.workspace import IsolatedWorkspace


@pytest.fixture
def temp_repo():
    """Create a temporary deterministic repository fixture."""
    tmp_dir = tempfile.mkdtemp(prefix="devaura_test_repo_")

    # Create dummy source files
    src_dir = os.path.join(tmp_dir, "pkg")
    os.makedirs(src_dir, exist_ok=True)

    math_file = os.path.join(src_dir, "calc.py")
    with open(math_file, "w", encoding="utf-8") as f:
        f.write("def divide(a, b):\n    return a / b\n")

    auth_file = os.path.join(src_dir, "auth.py")
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write("def parse_token(header):\n    return header.split()[1]\n")

    dict_file = os.path.join(src_dir, "handler.py")
    with open(dict_file, "w", encoding="utf-8") as f:
        f.write("def get_val(data):\n    return data['key']\n")

    test_file = os.path.join(tmp_dir, "test_calc.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def test_div():\n    assert True\n")

    yield tmp_dir

    shutil.rmtree(tmp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# Case 1: Single-file logic bug -> minimal patch applied to isolated sandbox
# -----------------------------------------------------------------------------
def test_case_1_single_file_logic_bug(temp_repo):
    context = RepairContext(
        repair_id="rep-1",
        investigation_id="inv-1",
        repository_id="repo-1",
        repository_path=temp_repo,
        failure={"failure_type": "RUNTIME_ERROR", "error_message": "ZeroDivisionError: division by zero"},
        selected_root_cause={"candidate_id": "c-1", "title": "Zero division in calc.py", "confidence": 0.95},
        supporting_evidence=[
            {"evidence_id": "ev-1", "repository_path": "pkg/calc.py", "line_start": 2, "content": "return a / b"}
        ],
        affected_files=["pkg/calc.py"],
        affected_lines={"pkg/calc.py": [2]},
    )

    planner = RepairPlanner()
    plan = planner.create_plan(context)
    assert len(plan.proposed_changes) == 1
    assert plan.proposed_changes[0].file == "pkg/calc.py"
    assert "ev-1" in plan.proposed_changes[0].evidence_ids

    generator = PatchGenerator(workspace_root=temp_repo)
    patch = generator.generate_defensive_patch(plan, context)
    assert patch.changed_files == ["pkg/calc.py"]
    assert patch.lines_added > 0

    # Risk analysis
    analyzer = PatchRiskAnalyzer()
    risk = analyzer.analyze(patch, plan, context)
    assert risk.level == PatchRiskLevel.LOW
    assert len(risk.blocking_findings) == 0

    # Human approval
    gate = HumanApprovalGate()
    approval = gate.create_approval(
        repair_id="rep-1",
        unified_diff=patch.unified_diff,
        user_identity="alice@example.com",
    )
    assert approval.status.value == "APPROVED"
    assert approval.patch_hash == patch.patch_hash

    # Apply strictly in isolated runner
    runner = IsolatedRunner()
    result = runner.run_patch_application(
        repair_id="rep-1",
        investigation_id="inv-1",
        repository_id="repo-1",
        source_repo_path=temp_repo,
        patch=patch,
    )
    assert result.application_status == "APPLIED"
    assert result.verification_status == "PENDING"

    # Verify original file untouched
    with open(os.path.join(temp_repo, "pkg", "calc.py"), "r", encoding="utf-8") as f:
        assert f.read() == "def divide(a, b):\n    return a / b\n"


# -----------------------------------------------------------------------------
# Case 2: Null/None guard addition
# -----------------------------------------------------------------------------
def test_case_2_none_guard_addition(temp_repo):
    context = RepairContext(
        repair_id="rep-2",
        investigation_id="inv-2",
        repository_id="repo-1",
        repository_path=temp_repo,
        failure={"failure_type": "RUNTIME_ERROR", "error_message": "AttributeError: 'NoneType' object has no attribute 'split'"},
        selected_root_cause={"candidate_id": "c-2", "title": "Missing None guard", "confidence": 0.90},
        supporting_evidence=[
            {"evidence_id": "ev-2", "repository_path": "pkg/auth.py", "line_start": 2, "content": "return header.split()[1]"}
        ],
        affected_files=["pkg/auth.py"],
        affected_lines={"pkg/auth.py": [2]},
    )

    planner = RepairPlanner()
    plan = planner.create_plan(context)
    assert plan.proposed_changes[0].change_type == "NULL_OR_NONE_GUARD"

    generator = PatchGenerator(workspace_root=temp_repo)
    patch = generator.generate_defensive_patch(plan, context)
    assert "None value" in patch.unified_diff


# -----------------------------------------------------------------------------
# Case 3: Unhandled KeyError / Boundary Check
# -----------------------------------------------------------------------------
def test_case_3_unhandled_keyerror_defensive_check(temp_repo):
    context = RepairContext(
        repair_id="rep-3",
        investigation_id="inv-3",
        repository_id="repo-1",
        repository_path=temp_repo,
        failure={"failure_type": "RUNTIME_ERROR", "error_message": "KeyError: 'key'"},
        selected_root_cause={"candidate_id": "c-3", "title": "Key not present in dictionary", "confidence": 0.85},
        supporting_evidence=[
            {"evidence_id": "ev-3", "repository_path": "pkg/handler.py", "line_start": 2, "content": "return data['key']"}
        ],
        affected_files=["pkg/handler.py"],
        affected_lines={"pkg/handler.py": [2]},
    )

    planner = RepairPlanner()
    plan = planner.create_plan(context)
    assert plan.proposed_changes[0].change_type == "BOUNDARY_OR_KEY_CHECK"


# -----------------------------------------------------------------------------
# Case 4: Multi-file coordinated repair bounded to evidence
# -----------------------------------------------------------------------------
def test_case_4_multi_file_coordinated_repair(temp_repo):
    context = RepairContext(
        repair_id="rep-4",
        investigation_id="inv-4",
        repository_id="repo-1",
        repository_path=temp_repo,
        failure={"failure_type": "TEST_FAILURE", "error_message": "Assertion failed across modules"},
        selected_root_cause={"candidate_id": "c-4", "title": "Interface mismatch", "confidence": 0.88},
        supporting_evidence=[
            {"evidence_id": "ev-4a", "repository_path": "pkg/calc.py", "line_start": 1, "content": "def divide"},
            {"evidence_id": "ev-4b", "repository_path": "pkg/auth.py", "line_start": 1, "content": "def parse_token"},
        ],
        affected_files=["pkg/calc.py", "pkg/auth.py"],
        affected_lines={"pkg/calc.py": [1], "pkg/auth.py": [1]},
    )

    planner = RepairPlanner()
    plan = planner.create_plan(context)
    assert len(plan.proposed_changes) == 2

    generator = PatchGenerator(workspace_root=temp_repo)
    patch = generator.generate_defensive_patch(plan, context)
    assert set(patch.changed_files) == {"pkg/calc.py", "pkg/auth.py"}


# -----------------------------------------------------------------------------
# Case 5: Out-of-scope file modification rejection
# -----------------------------------------------------------------------------
def test_case_5_out_of_scope_file_rejection(temp_repo):
    context = RepairContext(
        repair_id="rep-5",
        investigation_id="inv-5",
        repository_id="repo-1",
        repository_path=temp_repo,
        affected_files=["pkg/calc.py"],
    )
    plan = RepairPlan(
        repair_id="rep-5",
        investigation_id="inv-5",
        objective="Fix",
        root_cause="Bug",
        affected_files=["pkg/calc.py"],
    )
    generator = PatchGenerator(workspace_root=temp_repo)

    # Attempt to modify an unapproved file (pkg/handler.py)
    with pytest.raises(ScopeViolationError) as exc_info:
        generator.generate_from_content_map(
            plan=plan,
            context=context,
            modified_contents={"pkg/handler.py": "# unapproved change"},
        )
    assert "not in approved repair scope" in str(exc_info.value)


# -----------------------------------------------------------------------------
# Case 6: Path traversal attempt rejection
# -----------------------------------------------------------------------------
def test_case_6_path_traversal_rejection(temp_repo):
    guard = PatchScopeGuard()
    with pytest.raises(ScopeViolationError) as exc_info:
        guard.validate_file(temp_repo, "../outside.py", allowed_files=["pkg/calc.py"])
    assert "Path traversal" in str(exc_info.value)


# -----------------------------------------------------------------------------
# Case 7: Sensitive file modification rejection
# -----------------------------------------------------------------------------
def test_case_7_sensitive_file_rejection(temp_repo):
    guard = PatchScopeGuard()
    with pytest.raises(ScopeViolationError) as exc_info:
        guard.validate_file(temp_repo, ".env", allowed_files=[".env"])
    assert "sensitive file" in str(exc_info.value)

    with pytest.raises(ScopeViolationError):
        guard.validate_file(temp_repo, "secret.key", allowed_files=["secret.key"])


# -----------------------------------------------------------------------------
# Case 8: Dangerous execution / secret leakage detected by risk analyzer
# -----------------------------------------------------------------------------
def test_case_8_dangerous_execution_and_secrets(temp_repo):
    malicious_diff = """--- a/pkg/calc.py
+++ b/pkg/calc.py
@@ -1,2 +1,3 @@
 def divide(a, b):
+    eval(a)
     return a / b
"""
    patch = PatchResult(
        unified_diff=malicious_diff,
        patch_hash=hashlib.sha256(malicious_diff.strip().encode("utf-8")).hexdigest(),
        changed_files=["pkg/calc.py"],
        lines_added=1,
        lines_removed=0,
    )
    plan = RepairPlan(
        repair_id="rep-8",
        investigation_id="inv-8",
        objective="Fix",
        root_cause="Bug",
        affected_files=["pkg/calc.py"],
    )
    context = RepairContext(
        repair_id="rep-8",
        investigation_id="inv-8",
        repository_id="repo-1",
        repository_path=temp_repo,
        affected_files=["pkg/calc.py"],
    )

    analyzer = PatchRiskAnalyzer()
    risk = analyzer.analyze(patch, plan, context)
    assert risk.level == PatchRiskLevel.CRITICAL
    assert len(risk.blocking_findings) > 0
    assert any("eval()" in bf for bf in risk.blocking_findings)


# -----------------------------------------------------------------------------
# Case 9: Cryptographic patch tampering detected by approval gate
# -----------------------------------------------------------------------------
def test_case_9_cryptographic_patch_tampering(temp_repo):
    orig_diff = """--- a/pkg/calc.py
+++ b/pkg/calc.py
@@ -1,2 +1,3 @@
+    # safe guard
 def divide(a, b):
     return a / b
"""
    tampered_diff = """--- a/pkg/calc.py
+++ b/pkg/calc.py
@@ -1,2 +1,3 @@
+    # TAMPERED LINE
 def divide(a, b):
     return a / b
"""
    gate = HumanApprovalGate()
    approval = gate.create_approval(
        repair_id="rep-9",
        unified_diff=orig_diff,
        user_identity="reviewer@example.com",
    )

    # Validating original matches
    assert gate.verify_authorization(approval, orig_diff) is True

    # Validating tampered diff raises PatchIntegrityError
    with pytest.raises(PatchIntegrityError) as exc_info:
        gate.verify_authorization(approval, tampered_diff)
    assert "Cryptographic hash mismatch" in str(exc_info.value)

    # Self-approval forbidden
    with pytest.raises(ApprovalRequiredError):
        gate.create_approval(
            repair_id="rep-9",
            unified_diff=orig_diff,
            user_identity="agent",
        )


# -----------------------------------------------------------------------------
# Case 10: Insufficient investigation evidence blocks repair lifecycle
# -----------------------------------------------------------------------------
def test_case_10_insufficient_evidence_blocks_repair(temp_repo):
    builder = RepairContextBuilder(workspace_root=temp_repo)
    investigation = {
        "id": "inv-10",
        "repository_id": "repo-1",
        "status": "COMPLETED",
        "evidence_sufficiency": EvidenceSufficiency.INSUFFICIENT.value,
        "root_cause_candidates": [
            {"candidate_id": "c-10", "title": "Guessed cause", "supporting_evidence_ids": []}
        ],
        "evidence_items": [],
    }

    is_valid, ctx, err = builder.validate_and_build(investigation)
    assert is_valid is False
    assert ctx is None
    assert "INSUFFICIENT" in err


# -----------------------------------------------------------------------------
# Case 11: Native MCP Server Tools Integration
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_native_mcp_repair_tools_lifecycle(temp_repo):
    import json
    from mcp.server.devaura_server import create_devaura_native_server

    server = create_devaura_native_server()

    inv_data = {
        "id": "inv-mcp-1",
        "repository_id": "repo-mcp",
        "status": "COMPLETED",
        "evidence_sufficiency": "SUFFICIENT",
        "failure": {"failure_type": "RUNTIME_ERROR", "error_message": "ZeroDivisionError"},
        "root_cause_candidates": [
            {
                "candidate_id": "c-mcp-1",
                "title": "Division by zero",
                "affected_files": ["pkg/calc.py"],
                "supporting_evidence_ids": ["ev-1"],
            }
        ],
        "evidence_items": [
            {"evidence_id": "ev-1", "repository_path": "pkg/calc.py", "line_start": 2}
        ],
    }

    def extract_text(res):
        if hasattr(res, "content") and res.content:
            return res.content[0].text
        return str(res)

    # 1. create_repair_context
    ctx_out = await server.call_tool(
        "create_repair_context",
        arguments={
            "investigation_data": json.dumps(inv_data),
            "candidate_id": "c-mcp-1",
            "workspace": temp_repo,
            "repair_id": "rep-mcp-1",
        },
    )
    ctx_res = json.loads(extract_text(ctx_out))
    assert ctx_res["repair_id"] == "rep-mcp-1"

    # 2. get_repair_context
    get_ctx_out = await server.call_tool("get_repair_context", arguments={"repair_id": "rep-mcp-1"})
    assert "rep-mcp-1" in extract_text(get_ctx_out)

    # 3. generate_repair_plan
    plan_out = await server.call_tool("generate_repair_plan", arguments={"repair_id": "rep-mcp-1"})
    plan_res = json.loads(extract_text(plan_out))
    assert plan_res["repair_id"] == "rep-mcp-1"

    # 4. generate_patch
    patch_out = await server.call_tool(
        "generate_patch",
        arguments={"repair_id": "rep-mcp-1", "workspace": temp_repo},
    )
    patch_res = json.loads(extract_text(patch_out))
    assert patch_res["status"] == "GENERATED"
    patch_hash = patch_res["patch_hash"]

    # 5. analyze_patch_risk
    risk_out = await server.call_tool("analyze_patch_risk", arguments={"repair_id": "rep-mcp-1"})
    risk_res = json.loads(extract_text(risk_out))
    assert risk_res["level"] == "LOW"

    # 6. approve_repair
    appr_out = await server.call_tool(
        "approve_repair",
        arguments={
            "repair_id": "rep-mcp-1",
            "patch_hash": patch_hash,
            "approver_id": "auditor@devaura.ai",
        },
    )
    appr_res = json.loads(extract_text(appr_out))
    assert appr_res["status"] == "APPROVED"

    # 7. apply_approved_patch
    apply_out = await server.call_tool(
        "apply_approved_patch",
        arguments={"repair_id": "rep-mcp-1", "workspace": temp_repo},
    )
    apply_res = json.loads(extract_text(apply_out))
    assert apply_res["application_status"] == "APPLIED"
    assert apply_res["verification_status"] == "PENDING"

    # 8. get_repair_diff
    diff_out = await server.call_tool("get_repair_diff", arguments={"repair_id": "rep-mcp-1"})
    diff_res = json.loads(extract_text(diff_out))
    assert diff_res["patch_hash"] == patch_hash

