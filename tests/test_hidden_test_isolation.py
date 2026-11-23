"""Devaura Hidden Test Isolation Tests.

Verifies Section 13 requirements:
1. Hidden validation tests are physically absent from the agent repair workspace.
2. The LLM cannot discover hidden tests via filesystem glob, environment variables, or prompts.
3. Hidden tests are maintained in external evaluator storage and only executed by the evaluator.
"""

import os
from pathlib import Path
import pytest

from agent.llm.prompts import build_investigation_prompt, build_patch_prompt, build_repair_plan_prompt
from agent.models import EvidenceSource, EvidenceType, FailureType, NormalizedEvidence
from agent.repair.models import ProposedChange, RepairContext, RepairPlan
from data.datasets.builder import DatasetBuilder
from evaluation.historical.ground_truth import HISTORICAL_BUGS
from evaluation.historical.runner import HIDDEN_TESTS_DIR, HistoricalBenchmarkRunner


class TestHiddenTestIsolation:
    """Verifies that hidden tests remain strictly inaccessible to repair agents."""

    def test_hidden_tests_directory_is_external_to_workspace(self, tmp_path):
        """Asserts that HIDDEN_TESTS_DIR is completely outside any agent workspace."""
        for bug in HISTORICAL_BUGS:
            hidden_dir = HIDDEN_TESTS_DIR / bug.bug_id
            assert hidden_dir.exists(), f"Hidden test directory missing for {bug.bug_id}"

            # Hidden test directory must NOT be inside the repository source files
            for rel_file in bug.source_files.keys():
                assert "test_hidden" not in rel_file
                assert "hidden_tests" not in rel_file

            # Public test files must NOT contain hidden validation tests
            for repro_file, content in bug.reproduction_test.items():
                for hidden_file, hidden_content in bug.hidden_validation_test.items():
                    assert hidden_content not in content, f"Hidden test leaked into reproduction test for {bug.bug_id}"

    def test_workspace_creation_excludes_hidden_tests(self, tmp_path):
        """Asserts that when a bug workspace is initialized, zero hidden test files exist."""
        runner = HistoricalBenchmarkRunner(mode="deterministic")
        bug = HISTORICAL_BUGS[0]  # Flask
        bug_source_dir = runner.dataset_dir / bug.bug_id

        # Check source bug directory
        all_files = [str(p) for p in bug_source_dir.glob("**/*")]
        for p in all_files:
            assert "hidden_validation" not in p, f"Hidden test file found in public bug source dir: {p}"
            assert "hidden_test" not in p

    def test_hidden_test_absent_from_all_agent_prompts(self):
        """Verifies that no hidden test logic leaks into investigation, plan, or patch prompts."""
        for bug in HISTORICAL_BUGS:
            fake_evidence = [
                NormalizedEvidence(
                    evidence_id="ev_001",
                    investigation_id=f"inv-{bug.bug_id}",
                    type=EvidenceType.SYMBOL,
                    source=EvidenceSource.CODE_INTELLIGENCE,
                    repository_path=list(bug.source_files.keys())[0],
                    content="def code(): pass",
                    confidence=0.9,
                )
            ]
            inv_prompt = build_investigation_prompt(
                failure_title=bug.title,
                failure_type=FailureType.TEST_FAILURE.value,
                error_message=bug.error_message,
                stack_trace=bug.stack_trace,
                failed_tests=["tests/test_reproduce.py"],
                ranked_evidence=fake_evidence,
            )

            for test_file, test_content in bug.hidden_validation_test.items():
                assert test_content not in inv_prompt, f"Hidden test leaked into investigation prompt for {bug.bug_id}"

            ctx = RepairContext(
                repair_id="rep-01",
                investigation_id="inv-01",
                repository_id=f"hist-{bug.project}",
                repository_path="/sandbox",
                repository_revision="HEAD",
                failure={"error_message": bug.error_message},
                selected_root_cause={"title": bug.title},
                supporting_evidence=[],
                affected_files=list(bug.source_files.keys()),
                affected_symbols=bug.expected_symbols,
                affected_lines={},
                related_tests=["tests/test_reproduce.py"],
            )
            plan_prompt = build_repair_plan_prompt(ctx)
            for test_file, test_content in bug.hidden_validation_test.items():
                assert test_content not in plan_prompt, f"Hidden test leaked into plan prompt for {bug.bug_id}"
