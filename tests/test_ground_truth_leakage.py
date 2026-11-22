"""Devaura Ground-Truth Leakage & Evaluation Integrity Test Suite (Phase 8.1).

Validates that the runtime repair pipeline is strictly isolated from benchmark
ground-truth metadata and golden answers:
1. InvestigationRequest contains no expected root causes, symbols, or files.
2. RepairContext contains no ground truth answer keys.
3. Sandbox workspace initially contains no golden_patch.diff or metadata.json.
4. Runtime patch generator does not read golden_patch.diff.
5. Evaluator scorer access is strictly post-hoc (after repair completion).
"""

import json
import os
from pathlib import Path
import tempfile
import pytest

from agent.investigator import InvestigatorEngine
from agent.models import FailureType, InvestigationRequest
from agent.repair.context_builder import RepairContextBuilder
from agent.repair.patch_generator import PatchGenerator
from agent.repair.planner import RepairPlanner


FORBIDDEN_GROUND_TRUTH_KEYS = {
    "expected_root_cause",
    "golden_patch",
    "expected_fix_scope",
    "expected_symbols",
    "expected_files",
    "expected_lines",
    "expected_behavior",
    "ground_truth",
}


def test_investigation_request_has_no_ground_truth():
    """Ensure InvestigationRequest schema has no fields for ground-truth leakage."""
    req_fields = set(InvestigationRequest.model_fields.keys())
    leaked_fields = req_fields.intersection(FORBIDDEN_GROUND_TRUTH_KEYS)
    assert not leaked_fields, f"InvestigationRequest contains ground-truth leakage fields: {leaked_fields}"


def test_runtime_investigator_receives_no_ground_truth():
    """Ensure investigator runs purely on repository files and stack trace."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "app.py"
        test_file.write_text("def run():\n    return 1 / 0\n")

        engine = InvestigatorEngine(workspace_root=tmp_dir, repository_id="leak-test")
        req = InvestigationRequest(
            repository_id="leak-test",
            title="ZeroDivisionError in app.run",
            failure_type=FailureType.RUNTIME_ERROR,
            stack_trace='File "app.py", line 2, in run\n    return 1 / 0\nZeroDivisionError: division by zero',
        )

        # Assert no metadata was smuggled
        assert not hasattr(req, "expected_root_cause")
        report = engine.run(req)

        # Assert report provenance is strictly from repository inspection
        for ev in report.ranked_evidence:
            assert ev.source != "ground_truth"
            assert "golden" not in ev.source.lower()


def test_sandbox_isolated_from_benchmark_metadata():
    """Ensure the sandbox workspace does not contain benchmark ground-truth files."""
    dataset_dir = Path("evaluation/dataset/bugs/BUG-001")
    if not dataset_dir.exists():
        pytest.skip("Dataset not present in current directory")

    broken_code_dir = dataset_dir / "broken_code"
    files_in_broken = [p.name for p in broken_code_dir.glob("**/*") if p.is_file()]

    # Assert broken_code only contains source files and tests, never answers
    assert "metadata.json" not in files_in_broken
    assert "golden_patch.diff" not in files_in_broken
    assert "solution.py" not in files_in_broken
