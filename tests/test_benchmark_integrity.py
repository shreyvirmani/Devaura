"""Devaura Phase 9.4 Benchmark Integrity & Reliability Tests.

Automated verification of benchmark integrity, data flow isolation, and hardening:
1. Git Isolation Invariants: Verifies local git root, inaccessible fix_commit, reflog, and parent history.
2. Metadata & Hidden Test Isolation: Ensures bug_meta.json and hidden tests are absent from agent workspace.
3. PatchStructuralValidator (HIST-004 Hardening): Rejects Python syntax and indentation errors prior to verification.
4. Repository Manifest Invariant (HIST-009 Hardening): Rejects non-existent / hallucinated patch targets without git apply.
5. Baseline A Extraction Integrity: Verifies unassisted extraction without ground-truth cheats.
"""

import ast
import json
import os
from pathlib import Path
import subprocess
import pytest

from agent.llm.investigator import LLMInvestigator
from agent.llm.models import LLMInvestigationCandidate
from agent.llm.provider import ProviderFactory
from agent.repair.patch_generator import PatchScopeGuard, ScopeViolationError
from agent.repair.structural_validator import (
    PatchStructuralValidationError,
    PatchStructuralValidator,
)
from evaluation.historical.ground_truth import HISTORICAL_BUGS, HistoricalBugDefinition
from evaluation.historical.runner import (
    DATASET_DIR,
    HIDDEN_TESTS_DIR,
    HistoricalBenchmarkRunner,
)
from evaluation.schemas import ExecutionStatus, FailureCategory, RepairOutcomeState
from sandbox.workspace import IsolatedWorkspace


class TestGitWorkspaceIsolation:
    """Proves that IsolatedWorkspace enforces strict, non-traversing Git boundaries."""

    def test_git_top_level_stops_at_sandbox(self):
        bug = HISTORICAL_BUGS[0]  # HIST-001
        ws = IsolatedWorkspace(
            source_repo_path=str(DATASET_DIR / bug.bug_id),
            workspace_id="test_git_iso_top_level",
            buggy_commit=bug.buggy_commit,
        )
        sandbox_path = ws.create()
        try:
            # 1. git rev-parse --show-toplevel must return sandbox_path, NOT Devaura parent repo
            res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=sandbox_path,
                capture_output=True,
                text=True,
                check=True,
            )
            top_level = os.path.normpath(res.stdout.strip()).replace("\\", "/")
            expected = os.path.normpath(sandbox_path).replace("\\", "/")
            assert top_level.lower() == expected.lower(), f"Git top level traversed: {top_level} != {expected}"

            # 2. fix_commit is completely inaccessible in git object store
            cat_res = subprocess.run(
                ["git", "cat-file", "-e", bug.fix_commit],
                cwd=sandbox_path,
                capture_output=True,
                text=True,
            )
            assert cat_res.returncode != 0, f"Fix commit {bug.fix_commit} was accessible in git object store!"

            # 3. git show <fix_commit> fails
            show_res = subprocess.run(
                ["git", "show", bug.fix_commit],
                cwd=sandbox_path,
                capture_output=True,
                text=True,
            )
            assert show_res.returncode != 0, f"git show {bug.fix_commit} succeeded unexpectedly!"

            # 4. git log only contains buggy commit
            log_res = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=sandbox_path,
                capture_output=True,
                text=True,
                check=True,
            )
            assert bug.fix_commit not in log_res.stdout
            assert len(log_res.stdout.strip().splitlines()) == 1

            # 5. git reflog has NO fix commit
            reflog_res = subprocess.run(
                ["git", "reflog"],
                cwd=sandbox_path,
                capture_output=True,
                text=True,
                check=True,
            )
            assert bug.fix_commit not in reflog_res.stdout

            # 6. git remotes are completely empty
            remote_res = subprocess.run(
                ["git", "remote"],
                cwd=sandbox_path,
                capture_output=True,
                text=True,
                check=True,
            )
            assert remote_res.stdout.strip() == ""

        finally:
            ws.cleanup()

    def test_held_out_defects_git_isolation_invariants(self):
        """Verify git isolation for all 13 held-out test defects."""
        held_out_bugs = [b for b in HISTORICAL_BUGS if b.split == "test"]
        for bug in held_out_bugs:
            ws = IsolatedWorkspace(
                source_repo_path=str(DATASET_DIR / bug.bug_id),
                workspace_id=f"test_git_held_out_{bug.bug_id}",
                buggy_commit=bug.buggy_commit,
            )
            sandbox_path = ws.create()
            try:
                # Prove fix_commit cannot be read
                cat_res = subprocess.run(
                    ["git", "cat-file", "-e", bug.fix_commit],
                    cwd=sandbox_path,
                    capture_output=True,
                    text=True,
                )
                assert cat_res.returncode != 0, f"Fix commit {bug.fix_commit} leaked in {bug.bug_id}"
            finally:
                ws.cleanup()


class TestDataFlowAndMetadataIsolation:
    """Verifies that bug_meta.json and hidden tests are withheld from agent workspaces."""

    def test_bug_meta_json_excluded_from_agent_workspace(self):
        bug = HISTORICAL_BUGS[0]
        ws = IsolatedWorkspace(
            source_repo_path=str(DATASET_DIR / bug.bug_id),
            workspace_id="test_meta_exclusion",
        )
        sandbox_path = ws.create()
        try:
            meta_file = Path(sandbox_path) / "bug_meta.json"
            assert not meta_file.exists(), f"bug_meta.json leaked into agent workspace: {meta_file}"
        finally:
            ws.cleanup()

    def test_hidden_tests_physically_absent_from_workspace(self):
        held_out_bugs = [b for b in HISTORICAL_BUGS if b.split == "test"]
        for bug in held_out_bugs:
            ws = IsolatedWorkspace(
                source_repo_path=str(DATASET_DIR / bug.bug_id),
                workspace_id=f"test_hidden_absent_{bug.bug_id}",
            )
            sandbox_path = ws.create()
            try:
                for root, _, files in os.walk(sandbox_path):
                    for file in files:
                        assert "hidden" not in file.lower(), f"Hidden test file {file} leaked into {sandbox_path}"
            finally:
                ws.cleanup()


class TestPatchStructuralValidatorHardening:
    """Verifies Requirement 6: Structural AST validation (HIST-004 hardening)."""

    def test_structural_validator_rejects_syntax_errors(self, tmp_path):
        target_py = tmp_path / "service.py"
        target_py.write_text("def run():\n    return 42\n", encoding="utf-8")

        validator = PatchStructuralValidator(workspace_root=str(tmp_path))

        # Diff introducing a syntax error (missing colon, unexpected token)
        bad_syntax_diff = (
            "--- a/service.py\n"
            "+++ b/service.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-    return 42\n"
            "+    return return 42\n"
        )
        is_valid, err_msg, cat = validator.validate(bad_syntax_diff, ["service.py"])
        assert not is_valid
        assert cat == "PATCH_SYNTAX_FAILURE"
        assert "syntax error" in (err_msg or "").lower()

    def test_structural_validator_rejects_indentation_errors(self, tmp_path):
        target_py = tmp_path / "parser.py"
        target_py.write_text("def parse(x):\n    if x:\n        return x\n", encoding="utf-8")

        validator = PatchStructuralValidator(workspace_root=str(tmp_path))

        # Diff introducing a real indentation error (expected indented block)
        bad_indent_diff = (
            "--- a/parser.py\n"
            "+++ b/parser.py\n"
            "@@ -1,3 +1,3 @@\n"
            " def parse(x):\n"
            "-    if x:\n"
            "+if x:\n"  # Missing indent under def
            "         return x\n"
        )
        is_valid, err_msg, cat = validator.validate(bad_indent_diff, ["parser.py"])
        assert not is_valid
        assert cat == "PATCH_SYNTAX_FAILURE"
        assert "indent" in (err_msg or "").lower()


class TestRepositoryManifestInvariantHardening:
    """Verifies Requirement 7: Hard manifest constraint (HIST-009 hardening)."""

    def test_manifest_rejects_non_existent_file(self, tmp_path):
        validator = PatchStructuralValidator(workspace_root=str(tmp_path))

        # Propose patch to app/service.py which does not exist in workspace
        hallucinated_diff = (
            "--- a/app/service.py\n"
            "+++ b/app/service.py\n"
            "@@ -1,2 +1,3 @@\n"
            "+# added\n"
        )
        is_valid, err_msg, cat = validator.validate(hallucinated_diff, ["app/service.py"])
        assert not is_valid
        assert cat == "PATCH_SCOPE_FAILURE"
        assert "manifest violation" in (err_msg or "").lower()

    def test_investigator_candidate_filtering_rejects_non_existent_files(self, tmp_path):
        """LLMInvestigator._validate_candidates must discard candidates with non-existent paths."""
        provider = ProviderFactory.get_provider(mode="deterministic")
        inv = LLMInvestigator(workspace_root=str(tmp_path), provider=provider)

        # Candidate proposing hallucinated app/service.py
        raw_candidates = [
            LLMInvestigationCandidate(
                candidate_id="c1",
                statement="Hallucinated root cause in app/service.py",
                affected_files=["app/service.py"],
                affected_symbols=["run"],
                supporting_evidence_ids=["ev_001"],
                confidence=0.9,
            )
        ]
        validated = inv._validate_candidates(
            raw_candidates=raw_candidates,
            valid_evidence_ids={"ev_001"},
            ranked_evidence=[],
        )
        # Must be discarded because app/service.py does not exist in tmp_path
        assert len(validated) == 0


class TestBaselineAExtractionIntegrity:
    """Verifies Requirement 3: Baseline A performs genuine unassisted extraction without cheats."""

    def test_baseline_a_fails_localization_when_path_not_in_evidence(self):
        runner = HistoricalBenchmarkRunner(mode="deterministic")
        # HIST-004 stack trace only contains tests/test_reproduce.py (pydantic_core/parser.py is NOT in evidence)
        bug = next(b for b in HISTORICAL_BUGS if b.bug_id == "HIST-004")
        rec = runner.evaluate_single_bug(bug, run_index=1, baseline_mode="raw_llm")

        # Baseline A must NOT cheat by taking bug.source_files
        assert not rec.investigation.localized, "Baseline A cheated by localizing when path was absent from evidence!"
        assert rec.investigation.localization_rank is None
        assert rec.investigation.independently_inferred is True
        assert rec.investigation.evidence_provided_location is False
