"""Devaura LLM-Backed Investigator.

Leverages language models for root-cause synthesis and hypothesis generation,
governed by deterministic evidence citation validation and boundary defenses.
"""

import os
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agent.collector import EvidenceCollector
from agent.llm.models import (
    LLMInvestigationCandidate,
    LLMInvestigationResult,
    LLMUsage,
)
from agent.llm.prompts import (
    INVESTIGATION_SYSTEM_PROMPT,
    SecretRedactor,
    build_investigation_prompt,
)
from agent.llm.provider import LLMProvider, ProviderFactory
from agent.models import (
    EvidenceSufficiency,
    InvestigationReport,
    InvestigationRequest,
    InvestigationState,
    NormalizedEvidence,
    RootCauseCandidateSchema,
)
from agent.ranker import EvidenceRanker
from agent.state_machine import InvestigationStateMachine
from agent.sufficiency import EvidenceSufficiencyEvaluator
from apps.api.logger import logger


class LLMInvestigator:
    """Investigates software failures using an LLM governed by deterministic code intelligence."""

    def __init__(
        self,
        workspace_root: str,
        provider: Optional[LLMProvider] = None,
        repository_id: str = "default-repo",
    ):
        self.workspace_root = workspace_root
        self.repository_id = repository_id
        self.provider = provider or ProviderFactory.get_provider()
        self.collector = EvidenceCollector(
            workspace_root=workspace_root,
            investigation_id=str(uuid.uuid4()),
            repository_id=repository_id,
        )
        self.ranker = EvidenceRanker()
        self.sufficiency_evaluator = EvidenceSufficiencyEvaluator()

    def investigate(
        self,
        request: InvestigationRequest,
    ) -> Tuple[InvestigationReport, LLMUsage]:
        """Execute evidence-bounded investigation using an LLM.

        1. Deterministic evidence collection via Code Intelligence (AST, tests, git)
        2. Ranking & sufficiency evaluation
        3. Untrusted boundary prompt construction
        4. Structured LLM reasoning call
        5. Deterministic validation of evidence citations & candidate scoping
        """
        start_time = time.time()
        investigation_id = request.investigation_id or str(uuid.uuid4())
        self.collector.investigation_id = investigation_id

        # Step 1: Collect Evidence from Code Intelligence & environment (NO ground-truth leakage)
        raw_evidence, parsed_trace, parsed_tests = self.collector.collect_all_evidence(request)

        failing_file = None
        failing_symbol = None
        dependency_files: Set[str] = set()
        failed_test_files: Set[str] = set()

        if parsed_trace and parsed_trace.failing_frame:
            failing_file = parsed_trace.failing_frame.file
            failing_symbol = parsed_trace.failing_frame.symbol_id

        for pt in parsed_tests:
            if pt.test_file:
                failed_test_files.add(pt.test_file.replace("\\", "/"))
            if pt.tested_file:
                dependency_files.add(pt.tested_file.replace("\\", "/"))

        # Step 2: Rank evidence
        ranked_evidence = self.ranker.rank_evidence(
            raw_evidence,
            failing_file=failing_file,
            failing_symbol=failing_symbol,
            dependency_files=dependency_files,
            failed_test_files=failed_test_files,
        )

        # Step 3: Evaluate evidence sufficiency
        sufficiency, missing_info = self.sufficiency_evaluator.evaluate(
            evidence_list=ranked_evidence,
            error_message=request.error_message or "",
            has_stack_trace=bool(request.stack_trace),
            has_failed_tests=bool(request.failed_tests),
        )

        valid_evidence_ids = {e.evidence_id for e in ranked_evidence if e.evidence_id}

        # Step 4: Build prompt isolating untrusted code and inputs
        prompt = build_investigation_prompt(
            failure_title=request.title or f"Failure: {request.error_message[:80] if request.error_message else 'Unknown'}",
            failure_type=request.failure_type.value if hasattr(request.failure_type, "value") else str(request.failure_type),
            error_message=request.error_message or "No error message provided.",
            stack_trace=request.stack_trace or "",
            failed_tests=request.failed_tests or [],
            ranked_evidence=ranked_evidence[:15],
        )

        # Step 5: Call LLM with structured schema
        structured, usage = self.provider.generate_structured(
            prompt=prompt,
            schema=LLMInvestigationResult,
            system_prompt=INVESTIGATION_SYSTEM_PROMPT,
        )

        # Step 6: Deterministic Citation & Candidate Validation
        candidates: List[RootCauseCandidateSchema] = []
        if structured and structured.root_cause_candidates:
            candidates = self._validate_candidates(
                raw_candidates=structured.root_cause_candidates,
                valid_evidence_ids=valid_evidence_ids,
                ranked_evidence=ranked_evidence,
            )

        duration = round((time.time() - start_time) * 1000, 2)

        # Determine final summary & confidence
        if not candidates or sufficiency == EvidenceSufficiency.INSUFFICIENT:
            final_summary = "Insufficient evidence to determine root cause."
            overall_confidence = 0.0
            top_candidate = None
            recommended_steps = [
                "Provide a complete stack trace or reproduction script.",
                "Run unit/integration tests with verbose reporting enabled.",
                "Verify that the failing code path has been indexed by Code Intelligence.",
            ]
        else:
            top_candidate = candidates[0]
            overall_confidence = top_candidate.confidence
            final_summary = f"Identified {len(candidates)} root cause candidate(s). Leading hypothesis: {top_candidate.title}"
            recommended_steps = [
                "Formulate a bounded repair plan targeting the leading root cause.",
                "Review supporting evidence and verify test assertions.",
                "Execute surgical patch generation in an isolated sandbox.",
            ]

        report = InvestigationReport(
            investigation_id=investigation_id,
            repository_id=self.repository_id,
            status=InvestigationState.COMPLETED,
            evidence_sufficiency=sufficiency,
            summary=final_summary,
            root_cause_candidates=candidates,
            top_candidate=top_candidate,
            overall_confidence=overall_confidence,
            ranked_evidence=ranked_evidence,
            missing_information=missing_info,
            recommended_next_steps=recommended_steps,
            iteration_count=1,
            duration_ms=duration,
        )

        return report, usage

    def _validate_candidates(
        self,
        raw_candidates: List[LLMInvestigationCandidate],
        valid_evidence_ids: Set[str],
        ranked_evidence: List[NormalizedEvidence],
    ) -> List[RootCauseCandidateSchema]:
        """Validate LLM hypotheses against concrete evidence. Discards or penalizes hallucinated claims."""
        validated: List[RootCauseCandidateSchema] = []

        for c in raw_candidates:
            # Filter evidence IDs: only keep IDs that actually exist in collected evidence
            valid_cites = [eid for eid in c.supporting_evidence_ids if eid in valid_evidence_ids]

            # If the LLM cited evidence IDs but none were real, reject as hallucination
            if c.supporting_evidence_ids and not valid_cites:
                logger.warning(
                    f"Candidate '{c.candidate_id}' cited hallucinated evidence: {c.supporting_evidence_ids}. Discarding."
                )
                continue

            # If no supporting evidence was cited at all, check if evidence can be inferred from affected files
            if not valid_cites:
                inferred = [
                    e.evidence_id
                    for e in ranked_evidence
                    if e.repository_path in c.affected_files and e.evidence_id
                ]
                valid_cites = inferred[:3]

            # Enforce confidence bounds
            conf = min(max(c.confidence, 0.0), 1.0)
            if not valid_cites:
                conf = min(conf, 0.3)  # Heavy penalty for unbacked hypotheses

            # Normalize file paths
            clean_files = [f.replace("\\", "/").strip() for f in c.affected_files if f.strip()]

            schema = RootCauseCandidateSchema(
                candidate_id=c.candidate_id or f"RC-{uuid.uuid4().hex[:6]}",
                title=c.statement[:120] if c.statement else "Root Cause Candidate",
                description=c.statement or "Hypothesis proposed by LLM",
                confidence=round(conf, 2),
                affected_symbols=c.affected_symbols,
                affected_files=clean_files,
                supporting_evidence_ids=valid_cites,
                contradicting_evidence_ids=c.contradicting_evidence_ids,
                reasoning=c.uncertainty or "Identified through LLM analysis of code intelligence evidence.",
            )
            validated.append(schema)

        # Sort descending by confidence
        validated.sort(key=lambda x: x.confidence, reverse=True)
        return validated
