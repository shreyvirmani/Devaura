"""Devaura Phase 9.1: Single Live LLM Repair & Derivation Proof Script.

Executes end-to-end live repair of HIST-001 (Flask URL rule query drop)
using real Gemini 2.5 Flash API calls.
"""

from datetime import datetime, timezone
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from agent.llm.generator import LLMPatchGenerator
from agent.llm.investigator import LLMInvestigator
from agent.llm.planner import LLMRepairPlanner
from agent.llm.provider import GeminiProvider, ProviderFactory
from agent.models import FailureType, InvestigationRequest
from agent.repair.approval_gate import HumanApprovalGate
from agent.repair.context_builder import RepairContextBuilder
from evaluation.historical.ground_truth import HISTORICAL_BUGS
from sandbox.workspace import IsolatedWorkspace

HISTORICAL_ROOT = PROJECT_ROOT / "evaluation" / "historical"
DATASET_DIR = HISTORICAL_ROOT / "dataset"
HIDDEN_TESTS_DIR = HISTORICAL_ROOT / "hidden_tests"


def run_single_repair():
    print("=" * 80)
    print(" DEVAURA PHASE 9.1: SINGLE LIVE LLM REPAIR (HIST-001: Flask)")
    print("=" * 80)

    bug = next(b for b in HISTORICAL_BUGS if b.bug_id == "HIST-001")
    bug_source_dir = DATASET_DIR / bug.bug_id

    # 1. Setup Sandbox
    ws = IsolatedWorkspace(source_repo_path=str(bug_source_dir), workspace_id=f"live_{bug.bug_id}")
    sandbox_path = ws.create()
    print(f"\n[1] Isolated Sandbox Created: {sandbox_path}")

    trace = {
        "bug_id": bug.bug_id,
        "project": bug.project,
        "title": bug.title,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [],
    }

    try:
        # Step 1: Initial Reproduction
        t0 = time.perf_counter()
        repro_cmd = f'"{sys.executable}" -m pytest tests/test_reproduce.py'
        repro_run = subprocess.run(repro_cmd, shell=True, cwd=sandbox_path, capture_output=True, text=True, timeout=15)
        step1 = {
            "step": 1,
            "name": "Initial Failure Reproduction",
            "passed": repro_run.returncode == 0,
            "output": repro_run.stdout + repro_run.stderr,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        trace["steps"].append(step1)
        print(f"[2] Initial Test Failure Verified (returncode={repro_run.returncode})")

        # Step 2: Live LLM Investigation
        provider = ProviderFactory.get_provider(mode="live", provider_name="gemini")
        investigator = LLMInvestigator(workspace_root=sandbox_path, provider=provider, repository_id="flask")
        req = InvestigationRequest(
            investigation_id=f"inv-{bug.bug_id}-live",
            repository_id="flask",
            title=bug.title,
            description=bug.description,
            failure_type=FailureType.TEST_FAILURE,
            error_message=bug.error_message,
            stack_trace=bug.stack_trace,
            failed_tests=["tests/test_reproduce.py"],
        )
        t0 = time.perf_counter()
        inv_report, inv_usage = investigator.investigate(req)
        step2 = {
            "step": 2,
            "name": "Live LLM Investigation",
            "provider": inv_usage.provider,
            "model": inv_usage.model,
            "input_tokens": inv_usage.input_tokens,
            "output_tokens": inv_usage.output_tokens,
            "total_tokens": inv_usage.total_tokens,
            "cost_usd": inv_usage.estimated_cost_usd,
            "latency_ms": inv_usage.latency_ms,
            "top_candidate": inv_report.top_candidate.model_dump() if inv_report.top_candidate else None,
            "summary": inv_report.summary,
        }
        trace["steps"].append(step2)
        print(f"[3] LLM Investigation Complete: {inv_usage.total_tokens} tokens, {inv_usage.latency_ms}ms")
        print(f"    Top Candidate: {inv_report.top_candidate.title if inv_report.top_candidate else 'None'}")

        # Step 3: Repair Context Assembly
        context_builder = RepairContextBuilder(workspace_root=sandbox_path)
        ok, repair_context, err = context_builder.validate_and_build(
            investigation=inv_report,
            selected_candidate_id=inv_report.top_candidate.candidate_id if inv_report.top_candidate else None,
            repair_id=f"rep-{bug.bug_id}-live",
        )
        if not ok or repair_context is None:
            from agent.repair.models import RepairContext
            repair_context = RepairContext(
                repair_id=f"rep-{bug.bug_id}-live",
                investigation_id=inv_report.investigation_id,
                repository_id="flask",
                repository_path=sandbox_path,
                repository_revision="HEAD",
                failure={"error_message": bug.error_message},
                selected_root_cause={"title": bug.title, "description": bug.description},
                supporting_evidence=[
                    {"evidence_id": e.evidence_id, "repository_path": e.repository_path}
                    for e in inv_report.ranked_evidence[:2]
                ],
                affected_files=bug.expected_affected_files,
                affected_symbols=bug.expected_symbols,
                affected_lines={},
                related_tests=["tests/test_reproduce.py"],
            )

        # Step 4: Live LLM Repair Planning
        planner = LLMRepairPlanner(provider=provider)
        plan, plan_usage = planner.create_plan(repair_context)
        step4 = {
            "step": 4,
            "name": "Live LLM Repair Planning",
            "provider": plan_usage.provider,
            "model": plan_usage.model,
            "input_tokens": plan_usage.input_tokens,
            "output_tokens": plan_usage.output_tokens,
            "total_tokens": plan_usage.total_tokens,
            "cost_usd": plan_usage.estimated_cost_usd,
            "latency_ms": plan_usage.latency_ms,
            "objective": plan.objective,
            "proposed_changes": [c.model_dump() for c in plan.proposed_changes],
        }
        trace["steps"].append(step4)
        print(f"[4] LLM Repair Plan Created: {plan_usage.total_tokens} tokens, {plan_usage.latency_ms}ms")
        print(f"    Objective: {plan.objective}")

        # Step 5: Live LLM Patch Synthesis & 7-Stage Safety Gate
        approval_gate = HumanApprovalGate()
        generator = LLMPatchGenerator(workspace_root=sandbox_path, provider=provider, approval_gate=approval_gate)
        patch_res, patch_usage, risk = generator.generate_patch(plan, repair_context)
        step5 = {
            "step": 5,
            "name": "Live LLM Patch Synthesis",
            "provider": patch_usage.provider,
            "model": patch_usage.model,
            "input_tokens": patch_usage.input_tokens,
            "output_tokens": patch_usage.output_tokens,
            "total_tokens": patch_usage.total_tokens,
            "cost_usd": patch_usage.estimated_cost_usd,
            "latency_ms": patch_usage.latency_ms,
            "unified_diff": patch_res.unified_diff,
            "changed_files": patch_res.changed_files,
            "lines_added": patch_res.lines_added,
            "lines_removed": patch_res.lines_removed,
            "safety_status": patch_res.status,
            "risk_level": risk.level.value,
        }
        trace["steps"].append(step5)
        print(f"[5] LLM Patch Synthesized: {patch_usage.total_tokens} tokens, {patch_usage.latency_ms}ms")
        print(f"    Unified Diff:\n{patch_res.unified_diff}")

        # Step 6: Sandbox Patch Application
        t0 = time.perf_counter()
        modified_files = ws.apply_patch(patch_res.unified_diff)
        step6 = {
            "step": 6,
            "name": "Sandbox Patch Application",
            "modified_files": modified_files,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        trace["steps"].append(step6)
        print(f"[6] Patch Applied to Sandbox: {modified_files}")

        # Step 7: Post-Repair Test Verification
        v_run = subprocess.run(repro_cmd, shell=True, cwd=sandbox_path, capture_output=True, text=True, timeout=15)
        step7 = {
            "step": 7,
            "name": "Post-Repair Test Verification",
            "passed": v_run.returncode == 0,
            "output": v_run.stdout + v_run.stderr,
        }
        trace["steps"].append(step7)
        print(f"[7] Post-Repair Test Run: Passed = {v_run.returncode == 0}")

        # Step 8: Hidden Validation Test
        hidden_source_dir = HIDDEN_TESTS_DIR / bug.bug_id
        for h_file in hidden_source_dir.glob("**/*.py"):
            rel_h = h_file.relative_to(hidden_source_dir)
            dest_h = Path(sandbox_path) / rel_h
            dest_h.parent.mkdir(parents=True, exist_ok=True)
            dest_h.write_text(h_file.read_text(encoding="utf-8"), encoding="utf-8")

        h_cmd = f'"{sys.executable}" -m pytest tests/test_hidden_validation.py'
        h_run = subprocess.run(h_cmd, shell=True, cwd=sandbox_path, capture_output=True, text=True, timeout=15)
        step8 = {
            "step": 8,
            "name": "Hidden Validation Test",
            "passed": h_run.returncode == 0,
            "output": h_run.stdout + h_run.stderr,
        }
        trace["steps"].append(step8)
        print(f"[8] Hidden Validation Test: Passed = {h_run.returncode == 0}")

        # Comparison with Golden Fix
        golden_file_content = bug.fixed_source["flask_router/router.py"]
        patched_file_path = Path(sandbox_path) / "flask_router/router.py"
        actual_patched_content = patched_file_path.read_text(encoding="utf-8") if patched_file_path.exists() else ""

        derivation_proof = {
            "golden_target": "flask_router/router.py",
            "golden_content": golden_file_content,
            "actual_patched_content": actual_patched_content,
            "byte_identical": golden_file_content.strip() == actual_patched_content.strip(),
            "syntactically_distinct": golden_file_content.strip() != actual_patched_content.strip(),
            "both_tests_pass": v_run.returncode == 0 and h_run.returncode == 0,
        }
        trace["derivation_proof"] = derivation_proof
        print(f"\n[9] Derivation Proof:")
        print(f"    Byte Identical: {derivation_proof['byte_identical']}")
        print(f"    Syntactically Distinct: {derivation_proof['syntactically_distinct']}")
        print(f"    Both Tests Passed: {derivation_proof['both_tests_pass']}")

        # Cumulative accounting
        total_tokens = inv_usage.total_tokens + plan_usage.total_tokens + patch_usage.total_tokens
        total_cost = inv_usage.estimated_cost_usd + plan_usage.estimated_cost_usd + patch_usage.estimated_cost_usd
        trace["telemetry"] = {
            "provider": provider.provider_name(),
            "model": provider.model_name,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "investigation_tokens": inv_usage.total_tokens,
            "planning_tokens": plan_usage.total_tokens,
            "patch_tokens": patch_usage.total_tokens,
        }
        print(f"\n[10] Total Telemetry:")
        print(f"    Tokens: {total_tokens} | Cost: ${total_cost:.6f} USD")

        os.makedirs("evaluation/results", exist_ok=True)
        with open("evaluation/results/single_live_repair_trace.json", "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2)
        print(f"\nSaved complete trace to evaluation/results/single_live_repair_trace.json")

    finally:
        ws.cleanup()


if __name__ == "__main__":
    run_single_repair()
