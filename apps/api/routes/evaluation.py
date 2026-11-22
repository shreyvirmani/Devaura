"""Devaura Phase 8 Evaluation & Observability REST API Routes.

Exposes endpoints for:
1. Viewing summary benchmark metrics (M1-M14)
2. Browsing evaluation benchmark dataset bugs
3. Inspecting detailed evaluation results and ground truth
4. Triggering evaluation runs
5. Querying lifecycle and observability trace events
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from agent.events import tracker
from evaluation.dataset_builder import build_dataset
from evaluation.historical.runner import HistoricalBenchmarkRunner
from evaluation.runners.ablation_runner import AblationRunner
from evaluation.runners.benchmark_runner import BenchmarkRunner

router = APIRouter(prefix="/evaluation", tags=["Evaluation & Observability"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
RESULTS_DIR = BASE_DIR / "evaluation" / "results"
MANIFEST_PATH = BASE_DIR / "evaluation" / "dataset" / "manifest.json"


class RunEvaluationRequest(BaseModel):
    max_bugs: Optional[int] = Field(default=None, description="Limit execution to first N bugs")
    category: Optional[str] = Field(default=None, description="Optional category filter")


@router.get("/summary", summary="Get Latest Benchmark Summary Metrics")
async def get_benchmark_summary() -> Dict[str, Any]:
    """Retrieve the latest benchmark summary metrics (M1-M14)."""
    summary_file = RESULTS_DIR / "summary.json"
    if summary_file.exists():
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read evaluation summary: {e}",
            )

    # If summary doesn't exist yet, return baseline template
    return {
        "total_bugs": 25,
        "evaluated_bugs": 0,
        "successful_repairs": 0,
        "verification_pass_rate": 0.0,
        "regression_rate": 0.0,
        "false_repair_rate": 0.0,
        "total_safety_violations": 0,
        "is_deterministic": True,
        "status": "NOT_RUN",
    }


@router.get("/latest", summary="Get Full Latest Evaluation Run")
async def get_latest_results() -> Dict[str, Any]:
    """Retrieve full evaluation output with per-bug breakdown."""
    latest_file = RESULTS_DIR / "latest.json"
    if latest_file.exists():
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read latest results: {e}",
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No evaluation results found.")


@router.get("/bugs", summary="List Benchmark Dataset Bugs")
async def list_benchmark_bugs(
    category: Optional[str] = Query(None, description="Filter by category"),
) -> List[Dict[str, Any]]:
    """List benchmark bugs with metadata and category classification."""
    if not MANIFEST_PATH.exists():
        build_dataset()

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        bugs = data.get("bugs", []) if isinstance(data, dict) else data

    if category:
        bugs = [b for b in bugs if b.get("category", "").lower() == category.lower()]

    return bugs


@router.get("/bugs/{bug_id}", summary="Get Bug Details & Ground Truth")
async def get_bug_details(bug_id: str) -> Dict[str, Any]:
    """Retrieve metadata, golden diff, and execution result for a single bug."""
    bug_dir = BASE_DIR / "evaluation" / "dataset" / "bugs" / bug_id
    if not bug_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bug '{bug_id}' not found in benchmark dataset.",
        )

    meta_file = bug_dir / "metadata.json"
    diff_file = bug_dir / "golden_patch.diff"

    metadata = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    golden_diff = ""
    if diff_file.exists():
        with open(diff_file, "r", encoding="utf-8") as f:
            golden_diff = f.read()

    # Per-bug result if available
    result_file = RESULTS_DIR / "per_bug" / f"{bug_id}.json"
    eval_result = None
    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            eval_result = json.load(f)

    return {
        "bug_id": bug_id,
        "metadata": metadata,
        "golden_diff": golden_diff,
        "evaluation_result": eval_result,
    }


@router.post("/run", summary="Trigger Evaluation Benchmark Run")
async def run_evaluation(req: RunEvaluationRequest) -> Dict[str, Any]:
    """Execute evaluation across the benchmark dataset."""
    runner = BenchmarkRunner()
    summary = runner.run_all(max_bugs=req.max_bugs)
    return {
        "status": "COMPLETED",
        "total_evaluated": summary.evaluated_bugs,
        "successful_repairs": summary.successful_repairs,
        "verification_pass_rate": summary.verification_pass_rate,
        "safety_violations": summary.total_safety_violations,
        "summary": summary.model_dump(),
    }


@router.get("/events/{repair_id}", summary="Get Observability Lifecycle Events")
async def get_repair_events(repair_id: str) -> Dict[str, Any]:
    """Retrieve full lifecycle events and tool executions for a given repair."""
    events = tracker.get_events(repair_id)
    tool_calls = tracker.get_tool_executions(repair_id)

    return {
        "repair_id": repair_id,
        "event_count": len(events),
        "tool_call_count": len(tool_calls),
        "events": [e.to_dict() for e in events],
        "tool_executions": [t.to_dict() for t in tool_calls],
    }


@router.get("/historical", summary="Get Historical Real-World Benchmark Results (Track C)")
async def get_historical_benchmark() -> Dict[str, Any]:
    """Retrieve evaluation results across 10 real-world open-source defects (Track C)."""
    hist_file = RESULTS_DIR / "historical_metrics.json"
    if not hist_file.exists():
        # Fallback or run if not yet generated
        runner = HistoricalBenchmarkRunner()
        return runner.run_all()
    try:
        return json.loads(hist_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read historical benchmark results: {e}")


@router.post("/historical/run", summary="Trigger Track C Historical Benchmark Run")
async def run_historical_benchmark(max_bugs: Optional[int] = Query(default=None)) -> Dict[str, Any]:
    """Execute Track C evaluation across historical real-world defects."""
    runner = HistoricalBenchmarkRunner()
    metrics = runner.run_all(max_bugs=max_bugs)
    return {
        "status": "COMPLETED",
        "track": "Track C (Historical Real-World)",
        "total_bugs": metrics["total_bugs"],
        "correct_repair_rate": metrics["correct_repair_rate"],
        "metrics": metrics,
    }


@router.get("/ablation", summary="Get Phase 9 Ablation Study Results")
async def get_ablation_results() -> Dict[str, Any]:
    """Retrieve results for Architecture Impact and Evidence Ranking Ablation experiments."""
    ablation_file = RESULTS_DIR / "ablation_results.json"
    if not ablation_file.exists():
        runner = AblationRunner()
        return runner.run_all(sample_size=10)
    try:
        return json.loads(ablation_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read ablation results: {e}")


@router.post("/ablation/run", summary="Trigger Phase 9 Ablation Studies Run")
async def run_ablation_studies(sample_size: int = Query(default=10)) -> Dict[str, Any]:
    """Execute ablation experiments comparing Architecture and Evidence Ranking dimensions."""
    runner = AblationRunner()
    results = runner.run_all(sample_size=sample_size)
    return {
        "status": "COMPLETED",
        "results": results,
    }

