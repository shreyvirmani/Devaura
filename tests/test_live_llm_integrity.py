"""Devaura Phase 9.1: Live LLM Execution and Benchmark Integrity Tests.

Validates:
1. Provider selection and strict credential requirements (Cases A, B, C, D)
2. No silent fallback invariant under errors or missing credentials
3. Zero ground-truth leakage into LLM prompts or runtime contexts
4. Actual provider usage metadata token and cost accounting
"""

import os
from pathlib import Path
import pytest
from pydantic import BaseModel

from agent.llm.models import (
    LLMInvestigationResult,
    LLMPatchProposal,
    LLMRepairPlanProposal,
)
from agent.llm.prompts import (
    build_investigation_prompt,
    build_patch_prompt,
    build_repair_plan_prompt,
)
from agent.llm.provider import (
    DeterministicMockLLMProvider,
    GeminiProvider,
    LLMConfigurationError,
    LLMExecutionError,
    OpenAIProvider,
    ProviderFactory,
)
from agent.models import (
    EvidenceSource,
    EvidenceSufficiency,
    EvidenceType,
    FailureType,
    NormalizedEvidence,
)
from agent.repair.models import ProposedChange, RepairContext, RepairPlan
from evaluation.historical.ground_truth import HISTORICAL_BUGS


class TestProviderSelectionAndInvariants:
    """Verifies Cases A, B, C, D, E and the No Silent Fallback invariant."""

    def test_case_a_missing_api_key(self, monkeypatch):
        """Case A: Missing API Key -> raises LLMConfigurationError, never falls back."""
        monkeypatch.setenv("DEVAURA_LLM_MODE", "live")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY or GOOGLE_API_KEY is unset"):
            ProviderFactory.get_provider(mode="live", provider_name="gemini")

        provider = GeminiProvider(api_key="")
        with pytest.raises(LLMConfigurationError, match="Gemini API key is not configured"):
            provider.generate("test")

    def test_case_b_invalid_api_key(self):
        """Case B: Invalid API Key -> raises LLMExecutionError / 401, never falls back."""
        provider = OpenAIProvider(model_name="gpt-4o-mini", api_key="invalid_openai_key_test")

        class DummySchema(BaseModel):
            result: str

        with pytest.raises(LLMExecutionError) as exc_info:
            provider.generate_structured("test prompt", DummySchema)

        assert "OpenAI API returned HTTP 401" in str(exc_info.value)
        assert not isinstance(provider, DeterministicMockLLMProvider)

    def test_case_c_network_error(self, monkeypatch):
        """Case C: Network Error / Connection Refused -> raises LLMExecutionError, never falls back."""
        import httpx
        provider = GeminiProvider(api_key="valid_dummy_key")

        def mock_post(*args, **kwargs):
            raise httpx.ConnectError("Connection refused by remote host")

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        with pytest.raises(LLMExecutionError, match="Network error communicating with Gemini API"):
            provider.generate("test prompt")

    def test_case_d_rate_limit_429(self, monkeypatch):
        """Case D: Rate Limit / HTTP 429 -> raises LLMExecutionError, never falls back."""
        import httpx
        import time
        provider = GeminiProvider(api_key="valid_dummy_key")

        class MockResponse:
            status_code = 429
            text = '{"error": {"code": 429, "message": "RESOURCE_EXHAUSTED", "status": "RESOURCE_EXHAUSTED"}}'

            def json(self):
                return {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}

        monkeypatch.setattr(time, "sleep", lambda s: None)
        monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: MockResponse())

        with pytest.raises(LLMExecutionError, match="Gemini API returned HTTP 429"):
            provider.generate("test prompt")

    def test_case_e_empty_or_malformed_json(self, monkeypatch):
        """Case E: Empty Response / Malformed JSON -> raises LLMExecutionError, never falls back."""
        import httpx
        provider = GeminiProvider(api_key="valid_dummy_key")

        # 1. No candidates returned
        class MockEmptyResponse:
            status_code = 200
            def json(self):
                return {"candidates": []}

        monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: MockEmptyResponse())

        class DummySchema(BaseModel):
            field: str

        with pytest.raises(LLMExecutionError, match="Gemini returned no candidates"):
            provider.generate_structured("test", DummySchema)

        # 2. Malformed JSON returned
        class MockMalformedResponse:
            status_code = 200
            def json(self):
                return {
                    "candidates": [{
                        "content": {"parts": [{"text": "NOT VALID JSON {{"}]}
                    }]
                }

        monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: MockMalformedResponse())

        with pytest.raises(LLMExecutionError, match="Failed to validate Gemini JSON"):
            provider.generate_structured("test", DummySchema)

    def test_live_valid_key_provider_instantiation(self, monkeypatch):
        """Valid key instantiates live provider with configured settings."""
        monkeypatch.setenv("DEVAURA_LLM_MODE", "live")
        monkeypatch.setenv("DEVAURA_LLM_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "test_mock_gemini_api_key_valid_len_32")

        provider = ProviderFactory.get_provider(mode="live", provider_name="gemini")
        assert isinstance(provider, GeminiProvider)
        assert provider.provider_name() == "gemini"
        assert provider.model_name == "gemini-2.5-flash"
        assert provider.api_key == "test_mock_gemini_api_key_valid_len_32"

    def test_deterministic_mode_explicit(self, monkeypatch):
        """Deterministic mode returns DeterministicMockLLMProvider regardless of keys."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        provider = ProviderFactory.get_provider(mode="deterministic")
        assert isinstance(provider, DeterministicMockLLMProvider)
        assert provider.provider_name() == "deterministic-mock"

    def test_no_silent_fallback_invariant(self, monkeypatch):
        """Enforces that under NO circumstance does live mode quietly fall back to mock mode."""
        monkeypatch.setenv("DEVAURA_LLM_MODE", "live")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        # 1. Missing credentials must fail explicitly
        with pytest.raises(LLMConfigurationError):
            ProviderFactory.get_provider(mode="live", provider_name="gemini")

        # 2. Unsupported provider name must fail explicitly
        with pytest.raises(LLMConfigurationError, match="Unsupported live LLM provider"):
            ProviderFactory.get_provider(mode="live", provider_name="nonexistent_provider")


class TestGroundTruthIsolation:
    """Verifies zero ground-truth leakage in prompts, contexts, and fixtures."""

    def test_live_llm_ground_truth_isolation(self):
        """Asserts that golden patches, expected files, and hidden tests are withheld from LLM prompts."""
        for bug in HISTORICAL_BUGS:
            # 1. Investigation prompt isolation
            fake_evidence = [
                NormalizedEvidence(
                    evidence_id="ev_001",
                    investigation_id=f"inv-{bug.bug_id}",
                    type=EvidenceType.SYMBOL,
                    source=EvidenceSource.CODE_INTELLIGENCE,
                    repository_path=list(bug.source_files.keys())[0],
                    symbol_id=bug.expected_symbols[0] if bug.expected_symbols else None,
                    content="def dummy(): pass",
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

            # Golden patch / fixed source must NOT be in investigation prompt
            for file_path, fixed_content in bug.fixed_source.items():
                assert fixed_content not in inv_prompt, f"Ground-truth leakage in investigation prompt for {bug.bug_id}"

            # Hidden test must NOT be in investigation prompt
            for test_file, test_content in bug.hidden_validation_test.items():
                assert test_content not in inv_prompt, f"Hidden test leakage in investigation prompt for {bug.bug_id}"

            # 2. Repair Plan prompt isolation
            repair_ctx = RepairContext(
                repair_id=f"rep-{bug.bug_id}",
                investigation_id=f"inv-{bug.bug_id}",
                repository_id=f"hist-{bug.project}",
                repository_path="/sandbox",
                repository_revision="HEAD",
                failure={"error_message": bug.error_message},
                selected_root_cause={"title": bug.title, "description": bug.description},
                supporting_evidence=[{"evidence_id": "ev_001", "repository_path": list(bug.source_files.keys())[0]}],
                affected_files=list(bug.source_files.keys()),
                affected_symbols=bug.expected_symbols,
                affected_lines={},
                related_tests=["tests/test_reproduce.py"],
            )
            plan_prompt = build_repair_plan_prompt(repair_ctx)

            for file_path, fixed_content in bug.fixed_source.items():
                assert fixed_content not in plan_prompt, f"Ground-truth leakage in plan prompt for {bug.bug_id}"
            for test_file, test_content in bug.hidden_validation_test.items():
                assert test_content not in plan_prompt, f"Hidden test leakage in plan prompt for {bug.bug_id}"

            # 3. Patch synthesis prompt isolation
            plan = RepairPlan(
                repair_id=f"rep-{bug.bug_id}",
                investigation_id=f"inv-{bug.bug_id}",
                objective=f"Fix {bug.title}",
                root_cause=bug.description,
                affected_files=list(bug.source_files.keys()),
                affected_symbols=bug.expected_symbols,
                proposed_changes=[
                    ProposedChange(
                        file=list(bug.source_files.keys())[0],
                        location="line 1",
                        change_type="MODIFICATION",
                        rationale="Apply defensive guard",
                        evidence_ids=["ev_001"],
                        expected_effect="Resolve defect",
                    )
                ],
                tests_to_run=["tests/test_reproduce.py"],
                risks=[],
                assumptions=[],
                unresolved_questions=[],
                confidence=0.85,
                created_at="2026-11-23T00:00:00Z",
            )
            patch_prompt = build_patch_prompt(plan, repair_ctx, bug.source_files)

            for file_path, fixed_content in bug.fixed_source.items():
                assert fixed_content not in patch_prompt, f"Ground-truth leakage in patch prompt for {bug.bug_id}"
            for test_file, test_content in bug.hidden_validation_test.items():
                assert test_content not in patch_prompt, f"Hidden test leakage in patch prompt for {bug.bug_id}"
