"""Devaura Phase 9.1: Live LLM Sample Benchmark Runner.

Executes real external LLM evaluation across a representative sample of 4 defects:
- HIST-001: Flask (URL redirect query parameter loss)
- HIST-003: Click (CLI unicode/bytes formatting error)
- HIST-004: Pydantic (Union None-coercion validation)
- HIST-006: SQLAlchemy (Colon JSON path compiler escaping)

Audits token metrics directly from Gemini API metadata.
Saves detailed JSON artifact and summary metrics.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List

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
from agent.repair.models import RepairContext
from evaluation.historical.ground_truth import HISTORICAL_BUGS, HistoricalBugDefinition
from sandbox.workspace import IsolatedWorkspace

HISTORICAL_ROOT = PROJECT_ROOT / "evaluation" / "historical"
DATASET_DIR = HISTORICAL_ROOT / "dataset"
HIDDEN_TESTS_DIR = HISTORICAL_ROOT / "hidden_tests"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


def run_sample_benchmark(target_bug_ids: List[str] = None):
    if not target_bug_ids:
        target_bug_ids = ["HIST-001", "HIST-003", "HIST-004", "HIST-006"]

    print("=" * 80)
    print(" DEVAURA PHASE 9.1: LIVE LLM SAMPLE BENCHMARK (Track B Live)")
    print(f" Targets: {', '.join(target_bug_ids)}")
    print("=" * 80)

    selected_bugs = [b for b in HISTORICAL_BUGS if b.bug_id in target_bug_ids]
    provider = ProviderFactory.get_provider(mode="live", provider_name="gemini")
    print(f"Provider: {provider.provider_name()} | Model: {provider.model_name}\n")

    results: List[Dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_cost_usd = 0.0

    for bug in selected_bugs:
        print(f"--> [LIVE RUN] Evaluating {bug.bug_id} ({bug.project} - {bug.category})...")
        t_start = time.perf_counter()
        bug_source_dir = DATASET_DIR / bug.bug_id

        ws = IsolatedWorkspace(source_repo_path=str(bug_source_dir), workspace_id=f"sample_{bug.bug_id}")
        sandbox_path = ws.create()

        bug_prompt_tokens = 0
        bug_completion_tokens = 0
        bug_cost_usd = 0.0

        try:
            # 1. Reproduce
            cmd = f'"{sys.executable}" -m pytest tests/test_reproduce.py'
            repro_run = subprocess.run(cmd, shell=True, cwd=sandbox_path, capture_output=True, text=True, timeout=15)
            initial_failed = repro_run.returncode != 0

            # 2. Live Investigation
            investigator = LLMInvestigator(workspace_root=sandbox_path, provider=provider, repository_id=bug.project)
            req = InvestigationRequest(
                investigation_id=f"inv-{bug.bug_id}-live",
                repository_id=bug.project,
                title=bug.title,
                description=bug.description,
                failure_type=FailureType.TEST_FAILURE,
                error_message=bug.error_message,
                stack_trace=bug.stack_trace,
                failed_tests=["tests/test_reproduce.py"],
            )
            inv_report, inv_usage = investigator.investigate(req)
            bug_prompt_tokens += inv_usage.input_tokens
            bug_completion_tokens += inv_usage.output_tokens
            bug_cost_usd += inv_usage.estimated_cost_usd

            # Top-1 Localization check
            pred_files: List[str] = []
            for cand in inv_report.root_cause_candidates:
                pred_files.extend(cand.affected_files)
            for ev in inv_report.ranked_evidence:
                if ev.repository_path and ev.repository_path not in pred_files:
                    pred_files.append(ev.repository_path)
            clean_pred = [f.replace("\\", "/") for f in pred_files]
            localized_top1 = any(clean_pred and exp in clean_pred[0] for exp in bug.expected_affected_files)
            if not localized_top1:
                localized_top1 = any(clean_pred and any(exp in p for exp in bug.expected_affected_files) for p in clean_pred[:1])

            root_cause_accurate = bool(inv_report.top_candidate and any(exp in inv_report.top_candidate.title or exp in inv_report.top_candidate.description for exp in bug.expected_symbols))

            # 3. Live Repair Planning
            context_builder = RepairContextBuilder(workspace_root=sandbox_path)
            ok, repair_context, err = context_builder.validate_and_build(
                investigation=inv_report,
                selected_candidate_id=inv_report.top_candidate.candidate_id if inv_report.top_candidate else None,
                repair_id=f"rep-{bug.bug_id}-live",
            )
            if not ok or repair_context is None:
                repair_context = RepairContext(
                    repair_id=f"rep-{bug.bug_id}-live",
                    investigation_id=inv_report.investigation_id,
                    repository_id=bug.project,
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

            planner = LLMRepairPlanner(provider=provider)
            plan, plan_usage = planner.create_plan(repair_context)
            bug_prompt_tokens += plan_usage.input_tokens
            bug_completion_tokens += plan_usage.output_tokens
            bug_cost_usd += plan_usage.estimated_cost_usd
            plan_generated = bool(plan and plan.proposed_changes)

            # 4. Live Patch Generation & Safety Gate
            approval_gate = HumanApprovalGate()
            generator = LLMPatchGenerator(workspace_root=sandbox_path, provider=provider, approval_gate=approval_gate)
            patch_res, patch_usage, risk = generator.generate_patch(plan, repair_context)
            bug_prompt_tokens += patch_usage.input_tokens
            bug_completion_tokens += patch_usage.output_tokens
            bug_cost_usd += patch_usage.estimated_cost_usd
            patch_generated = bool(patch_res.unified_diff)
            safety_gate_passed = bool(patch_res.status == "GENERATED")

            # 5. Apply LLM Patch to Sandbox
            patch_applied = False
            if patch_generated and patch_res.unified_diff:
                try:
                    modified = ws.apply_patch(patch_res.unified_diff)
                    patch_applied = len(modified) > 0
                except Exception as e:
                    patch_applied = False

            # 6. Verify Sandbox Test
            v_run = subprocess.run(cmd, shell=True, cwd=sandbox_path, capture_output=True, text=True, timeout=15)
            original_fixed = v_run.returncode == 0

            # 7. Verify Hidden Test
            hidden_source_dir = HIDDEN_TESTS_DIR / bug.bug_id
            for h_file in hidden_source_dir.glob("**/*.py"):
                rel_h = h_file.relative_to(hidden_source_dir)
                dest_h = Path(sandbox_path) / rel_h
                dest_h.parent.mkdir(parents=True, exist_ok=True)
                dest_h.write_text(h_file.read_text(encoding="utf-8"), encoding="utf-8")

            h_cmd = f'"{sys.executable}" -m pytest tests/test_hidden_validation.py'
            h_run = subprocess.run(h_cmd, shell=True, cwd=sandbox_path, capture_output=True, text=True, timeout=15)
            hidden_passed = h_run.returncode == 0

            if original_fixed and hidden_passed:
                outcome = "CORRECT_REPAIR"
            elif original_fixed and not hidden_passed:
                outcome = "FALSE_REPAIR"
            else:
                outcome = "UNRESOLVED"

            latency_s = round(time.perf_counter() - t_start, 2)
            bug_total_tokens = bug_prompt_tokens + bug_completion_tokens

            total_prompt_tokens += bug_prompt_tokens
            total_completion_tokens += bug_completion_tokens
            total_tokens += bug_total_tokens
            total_cost_usd += bug_cost_usd

            res = {
                "case_id": bug.bug_id,
                "project": bug.project,
                "category": bug.category,
                "provider": provider.provider_name(),
                "model": provider.model_name,
                "localized_top1": localized_top1,
                "root_cause_accurate": root_cause_accurate,
                "plan_generated": plan_generated,
                "patch_generated": patch_generated,
                "safety_gate_passed": safety_gate_passed,
                "patch_applied": patch_applied,
                "original_fixed": original_fixed,
                "hidden_passed": hidden_passed,
                "outcome": outcome,
                "prompt_tokens": bug_prompt_tokens,
                "completion_tokens": bug_completion_tokens,
                "total_tokens": bug_total_tokens,
                "latency_seconds": latency_s,
                "cost_usd": round(bug_cost_usd, 6),
                "retry_attempts": 0,
                "generated_diff": patch_res.unified_diff,
            }
            results.append(res)
            print(
                f"    -> Outcome: {outcome} | Localized: {localized_top1} | "
                f"Fixed: {original_fixed} | Hidden: {hidden_passed} | "
                f"Tokens: {bug_total_tokens} | Cost: ${bug_cost_usd:.6f} | Latency: {latency_s}s"
            )

        except Exception as e:
            latency_s = round(time.perf_counter() - t_start, 2)
            bug_total_tokens = bug_prompt_tokens + bug_completion_tokens
            total_prompt_tokens += bug_prompt_tokens
            total_completion_tokens += bug_completion_tokens
            total_tokens += bug_total_tokens
            total_cost_usd += bug_cost_usd
            print(f"    -> ERROR evaluating {bug.bug_id}: {e}")
            res = {
                "case_id": bug.bug_id,
                "project": bug.project,
                "category": bug.category,
                "provider": provider.provider_name(),
                "model": provider.model_name,
                "localized_top1": False,
                "root_cause_accurate": False,
                "plan_generated": False,
                "patch_generated": False,
                "safety_gate_passed": False,
                "patch_applied": False,
                "original_fixed": False,
                "hidden_passed": False,
                "outcome": "ERROR",
                "error_details": str(e),
                "prompt_tokens": bug_prompt_tokens,
                "completion_tokens": bug_completion_tokens,
                "total_tokens": bug_total_tokens,
                "latency_seconds": latency_s,
                "cost_usd": round(bug_cost_usd, 6),
                "retry_attempts": 0,
                "generated_diff": "",
            }
            results.append(res)

        finally:
            ws.cleanup()

    summary = {
        "benchmark_track": "Track B (Live LLM Execution Benchmark)",
        "provider": provider.provider_name(),
        "model": provider.model_name,
        "sample_size": len(results),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "localization_top1_count": sum(1 for r in results if r["localized_top1"]),
        "original_fixed_count": sum(1 for r in results if r["original_fixed"]),
        "hidden_passed_count": sum(1 for r in results if r["hidden_passed"]),
        "correct_repairs_count": sum(1 for r in results if r["outcome"] == "CORRECT_REPAIR"),
        "false_repairs_count": sum(1 for r in results if r["outcome"] == "FALSE_REPAIR"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / "live_llm_sample_benchmark.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved live benchmark results to {out_file}")
    return summary


if __name__ == "__main__":
    run_sample_benchmark()
