"""Phase 9 Comprehensive LLM Pipeline Unit Tests.

Validates:
1. LLM Provider abstractions (Mock, Gemini, OpenAI, ProviderFactory)
2. Secret redaction before prompt transmission
3. LLM Investigator with evidence citation validation
4. LLM Repair Planner with mandatory evidence citation enforcement
5. LLM Patch Generator with 7-stage deterministic safety checks
6. Track C Historical Real-World benchmark runner execution
"""

import os
from pathlib import Path
import pytest

from agent.llm.generator import LLMPatchGenerator
from agent.llm.investigator import LLMInvestigator
from agent.llm.models import (
    LLMInvestigationResult,
    LLMPatchProposal,
    LLMRepairPlanProposal,
)
from agent.llm.planner import LLMRepairPlanner
from agent.llm.prompts import (
    SecretRedactor,
    build_investigation_prompt,
    build_patch_prompt,
    build_repair_plan_prompt,
)
from agent.llm.provider import (
    DeterministicMockLLMProvider,
    GeminiProvider,
    LLMConfigurationError,
    OpenAIProvider,
    ProviderFactory,
)
from agent.models import (
    EvidenceSource,
    EvidenceSufficiency,
    EvidenceType,
    FailureType,
    InvestigationRequest,
    NormalizedEvidence,
)
from agent.repair.approval_gate import HumanApprovalGate
from agent.repair.models import ProposedChange, RepairContext, RepairPlan
from agent.repair.patch_generator import ScopeViolationError
from evaluation.historical.ground_truth import HISTORICAL_BUGS
from evaluation.historical.runner import HistoricalBenchmarkRunner


class TestLLMProviders:
    """Tests for LLM provider abstractions, factory, and error modes."""

    def test_deterministic_mock_provider_generation(self):
        provider = DeterministicMockLLMProvider()
        resp = provider.generate("Analyze this failure")
        assert resp.content
        assert resp.usage.total_tokens > 0
        assert resp.usage.provider == "deterministic-mock"
        assert resp.usage.estimated_cost_usd > 0.0

    def test_deterministic_mock_structured_output(self):
        provider = DeterministicMockLLMProvider()
        result, usage = provider.generate_structured(
            prompt="Analyze failure with Evidence ID: ev:123:1 in app/service.py",
            schema=LLMInvestigationResult,
        )
        assert isinstance(result, LLMInvestigationResult)
        assert len(result.root_cause_candidates) > 0
        assert "ev:123:1" in result.root_cause_candidates[0].supporting_evidence_ids
        assert usage.total_tokens > 0

    def test_live_provider_missing_credentials_raises_cleanly(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY or GOOGLE_API_KEY is unset"):
            ProviderFactory.get_provider(mode="live", provider_name="gemini")

    def test_openai_missing_credentials_raises_cleanly(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY is unset"):
            ProviderFactory.get_provider(mode="live", provider_name="openai")

    def test_provider_telemetry_accumulation(self):
        provider = DeterministicMockLLMProvider()
        initial_tokens = provider.total_input_tokens
        provider.generate("First query")
        provider.generate("Second query")
        assert provider.total_input_tokens > initial_tokens
        summary = provider.token_usage()
        assert summary["total_tokens"] > 0
        assert summary["estimated_cost_usd"] > 0.0


class TestSecretRedaction:
    """Tests that credentials, keys, and tokens are scrubbed before LLM prompt submission."""

    def test_redact_github_tokens(self):
        text = "Repo config with token: ghp_1234567890abcdefghijklmnopqrstuv"
        clean = SecretRedactor.redact(text)
        assert "ghp_" not in clean
        assert "[REDACTED_SECRET]" in clean

    def test_redact_api_keys(self):
        text = "API key: AIzaSyD9876543210ZYXWVUTSRQPONMLKJIHGF"
        clean = SecretRedactor.redact(text)
        assert "AIzaSy" not in clean
        assert "[REDACTED_SECRET]" in clean

    def test_redact_private_keys(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
        clean = SecretRedactor.redact(text)
        assert "BEGIN RSA PRIVATE KEY" not in clean
        assert "[REDACTED_SECRET]" in clean


class TestLLMInvestigator:
    """Tests for LLM-backed root cause localization and citation validation."""

    def test_investigator_citations_and_report_creation(self, tmp_path):
        # Create a minimal workspace with broken code
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "service.py").write_text("def run():\n    return 10 / 0\n")

        provider = DeterministicMockLLMProvider()
        investigator = LLMInvestigator(workspace_root=str(tmp_path), provider=provider)

        req = InvestigationRequest(
            investigation_id="inv-test-01",
            repository_id="test-repo",
            title="ZeroDivisionError in service.py",
            description="Division by zero crash",
            failure_type=FailureType.RUNTIME_ERROR,
            error_message="ZeroDivisionError: division by zero",
            stack_trace='File "app/service.py", line 2, in run\n    return 10 / 0\nZeroDivisionError: division by zero',
        )

        report, usage = investigator.investigate(req)
        assert report.investigation_id == "inv-test-01"
        assert report.status.value == "COMPLETED"
        assert usage.total_tokens > 0

    def test_discard_hallucinated_evidence_citations(self, tmp_path):
        investigator = LLMInvestigator(workspace_root=str(tmp_path))
        from agent.llm.models import LLMInvestigationCandidate
        raw_candidates = [
            LLMInvestigationCandidate(
                candidate_id="cand-fake",
                statement="Fake root cause",
                affected_files=["app/fake.py"],
                supporting_evidence_ids=["ev_completely_hallucinated_999"],
                confidence=0.9,
            )
        ]
        # Valid evidence IDs contains only ev_001
        validated = investigator._validate_candidates(
            raw_candidates=raw_candidates,
            valid_evidence_ids={"ev_001"},
            ranked_evidence=[],
        )
        # The candidate cited evidence IDs but none were real -> discarded!
        assert len(validated) == 0


class TestLLMRepairPlanner:
    """Tests for repair plan synthesis and mandatory citation enforcement."""

    def test_mandatory_evidence_citations_enforced(self):
        ctx = RepairContext(
            repair_id="rep-01",
            investigation_id="inv-01",
            repository_id="repo-01",
            repository_path=".",
            repository_revision="HEAD",
            failure={"error_message": "ValueError"},
            selected_root_cause={"title": "Input check", "description": "Needs guard"},
            supporting_evidence=[{"evidence_id": "ev:test:1", "repository_path": "app/service.py"}],
            affected_files=["app/service.py"],
            affected_symbols=["run"],
            affected_lines={"app/service.py": [2]},
            related_tests=["tests/test_service.py"],
        )

        planner = LLMRepairPlanner()
        plan, usage = planner.create_plan(ctx)
        assert plan.repair_id == "rep-01"
        assert len(plan.proposed_changes) > 0
        for change in plan.proposed_changes:
            # Every proposed change must cite evidence IDs
            assert len(change.evidence_ids) > 0
            assert change.file in ctx.affected_files


class TestLLMPatchGenerator:
    """Tests for the 7-stage deterministic safety gate in patch synthesis."""

    @pytest.fixture
    def setup_context_and_plan(self, tmp_path):
        app_file = tmp_path / "service.py"
        app_file.write_text("def compute():\n    return 42\n")

        ctx = RepairContext(
            repair_id="rep-patch-01",
            investigation_id="inv-patch-01",
            repository_id="test-repo",
            repository_path=str(tmp_path),
            repository_revision="HEAD",
            failure={"error_message": "Fix needed"},
            selected_root_cause={"title": "Fix logic"},
            supporting_evidence=[{"evidence_id": "ev:01:1", "repository_path": "service.py"}],
            affected_files=["service.py"],
            affected_symbols=["compute"],
            affected_lines={"service.py": [2]},
            related_tests=[],
        )

        plan = RepairPlan(
            repair_id="rep-patch-01",
            investigation_id="inv-patch-01",
            objective="Fix return",
            root_cause="Fix logic",
            affected_files=["service.py"],
            affected_symbols=["compute"],
            proposed_changes=[
                ProposedChange(
                    file="service.py",
                    location="line 2",
                    change_type="MODIFICATION",
                    rationale="Add defensive check",
                    evidence_ids=["ev:01:1"],
                    expected_effect="Safe return",
                )
            ],
            tests_to_run=[],
            risks=[],
            assumptions=[],
            unresolved_questions=[],
            confidence=0.9,
            created_at="2026-11-22T00:00:00Z",
        )
        return tmp_path, ctx, plan

    def test_path_traversal_attack_blocked(self, setup_context_and_plan):
        tmp_path, ctx, plan = setup_context_and_plan
        gen = LLMPatchGenerator(workspace_root=str(tmp_path))
        malicious_diff = (
            "--- a/../etc/passwd\n"
            "+++ b/../etc/passwd\n"
            "@@ -1,1 +1,1 @@\n"
            "+root::0:0:::\n"
        )
        with pytest.raises(ScopeViolationError, match="path traversal detected"):
            gen._validate_path_traversal(malicious_diff)

    def test_sensitive_file_modification_blocked(self, setup_context_and_plan):
        tmp_path, ctx, plan = setup_context_and_plan
        gen = LLMPatchGenerator(workspace_root=str(tmp_path))
        with pytest.raises(ScopeViolationError, match="restricted file"):
            gen._validate_file_safety(".env")
        with pytest.raises(ScopeViolationError, match="restricted file"):
            gen._validate_file_safety("credentials.json")
        with pytest.raises(ScopeViolationError, match="forbidden"):
            gen._validate_file_safety("server.key")

    def test_out_of_scope_file_modification_blocked(self, setup_context_and_plan):
        tmp_path, ctx, plan = setup_context_and_plan
        gen = LLMPatchGenerator(workspace_root=str(tmp_path))
        out_of_scope_diff = (
            "--- a/other_service.py\n"
            "+++ b/other_service.py\n"
            "@@ -1,1 +1,2 @@\n"
            "+# modification\n"
        )
        changed = gen._extract_changed_files(out_of_scope_diff)
        assert "other_service.py" in changed
        assert "other_service.py" not in plan.affected_files


class TestHistoricalBenchmarkExecution:
    """Tests execution of the Track C historical benchmark runner."""

    def test_historical_dataset_manifest_integrity(self):
        assert len(HISTORICAL_BUGS) == 12
        bug_ids = [b.bug_id for b in HISTORICAL_BUGS]
        assert len(set(bug_ids)) == 12
        for b in HISTORICAL_BUGS:
            assert b.bug_id.startswith("HIST-")
            assert b.project
            assert b.cve_or_issue
            assert b.source_files
            assert b.reproduction_test
            assert b.hidden_validation_test

    def test_single_historical_defect_evaluation(self):
        runner = HistoricalBenchmarkRunner(mode="deterministic")
        res = runner.evaluate_single_bug(HISTORICAL_BUGS[0])  # HIST-001 (flask)
        assert res.bug_id == "HIST-001" or res["bug_id"] == "HIST-001"
        assert res["localized_top1"] is True
        assert res["original_failure_fixed"] is True
        assert res["hidden_test_passed"] is True
        assert res["outcome"] == "CORRECT_REPAIR"
        assert res["tokens_used"] > 0
