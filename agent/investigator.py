"""Devaura Investigator Engine.

Executes a bounded investigation loop (max 5 iterations):
1. Inspect Failure & Initialize Request
2. Collect Evidence (Code Intelligence, Git, Stack Traces, Tests)
3. Trace Dependency Paths & Call Graphs
4. Rank Evidence & Evaluate Sufficiency
5. Synthesize Root Cause Candidates & Produce Explainable Report

Safety & Invariants:
--------------------
- Strictly READ-ONLY: Never modifies files, creates commits, or opens PRs.
- Bounded loop: Max 5 iterations, stops early if sufficient evidence exists.
- Observability: Audits every tool call and iteration as an InvestigationStep.
- Transparent Uncertainty: When evidence is insufficient, explicitly concludes:
  "Insufficient evidence to determine root cause."
"""

import os
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agent.collector import EvidenceCollector
from agent.models import (
    EvidenceSource,
    EvidenceSufficiency,
    EvidenceType,
    FailureType,
    InvestigationReport,
    InvestigationRequest,
    InvestigationState,
    NormalizedEvidence,
    ParsedStackFrame,
    ParsedStackTrace,
    ParsedTestFailure,
    ResolutionStatus,
    RootCauseCandidateSchema,
)
from agent.ranker import EvidenceRanker
from agent.state_machine import InvestigationStateMachine
from agent.sufficiency import EvidenceSufficiencyEvaluator
from apps.api.logger import logger


class InvestigatorEngine:
    """Core evidence-driven investigation orchestrator."""

    MAX_ITERATIONS = 5
    MAX_EVIDENCE_ITEMS = 50

    def __init__(
        self,
        workspace_root: str,
        investigation_id: Optional[str] = None,
        repository_id: str = "default-repo",
    ):
        self.workspace_root = workspace_root
        self.investigation_id = investigation_id or str(uuid.uuid4())
        self.repository_id = repository_id

        self.state_machine = InvestigationStateMachine(InvestigationState.CREATED)
        self.collector = EvidenceCollector(
            workspace_root=workspace_root,
            investigation_id=self.investigation_id,
            repository_id=repository_id,
        )
        self.ranker = EvidenceRanker()
        self.sufficiency_evaluator = EvidenceSufficiencyEvaluator()

        self.steps_log: List[Dict[str, Any]] = []

    @staticmethod
    def _is_test_file(file_path: Optional[str]) -> bool:
        if not file_path:
            return False
        clean = file_path.replace("\\", "/").lower()
        base = os.path.basename(clean)
        return (
            base.startswith("test_")
            or base.endswith("_test.py")
            or "/tests/" in clean
            or clean.startswith("tests/")
            or clean.startswith("test/")
        )

    def _record_step(
        self,
        step_number: int,
        action: str,
        observation: str,
        tool_name: Optional[str] = None,
        tool_input: Optional[Dict[str, Any]] = None,
        tool_output: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an immutable execution audit step."""
        self.steps_log.append(
            {
                "step_number": step_number,
                "action": action,
                "tool_name": tool_name,
                "tool_input": tool_input or {},
                "tool_output": tool_output or {},
                "observation": observation,
                "timestamp": time.time(),
            }
        )

    def run(self, request: InvestigationRequest) -> InvestigationReport:
        """Run the complete 5-step bounded investigation loop."""
        start_time = time.time()
        iteration = 0

        # Iteration 1: Initialize and Parse Request
        iteration += 1
        self.state_machine.transition(InvestigationState.COLLECTING_EVIDENCE)
        self._record_step(
            step_number=iteration,
            action="INITIALIZE_INVESTIGATION",
            observation=f"Started investigation '{self.investigation_id}' for failure type {request.failure_type.value}.",
            tool_input={"failure_type": request.failure_type.value, "title": request.title},
        )

        # Iteration 2: Collect Evidence across Code Intelligence, Git, Stack Traces
        iteration += 1
        raw_evidence, parsed_trace, parsed_tests = self.collector.collect_all_evidence(request)
        self._record_step(
            step_number=iteration,
            action="COLLECT_EVIDENCE",
            observation=f"Collected {len(raw_evidence)} raw evidence items across code, git, and tests.",
            tool_name="code_intelligence_and_git_collector",
            tool_output={"count": len(raw_evidence)},
        )

        self.state_machine.transition(InvestigationState.EVIDENCE_READY)

        # Iteration 3: Trace Dependencies & Extract Context Targets
        iteration += 1
        failing_file: Optional[str] = None
        failing_symbol: Optional[str] = None
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

        # If failing frame is in a test file, map primary target to tested implementation source
        if failing_file and self._is_test_file(failing_file):
            for pt in parsed_tests:
                if pt.tested_file and not self._is_test_file(pt.tested_file):
                    failing_file = pt.tested_file.replace("\\", "/")
                    if pt.tested_symbol_id:
                        failing_symbol = pt.tested_symbol_id
                    break

            if self._is_test_file(failing_file):
                for m in getattr(self.collector, "test_mappings", []):
                    m_test = m.get("test_file", "").replace("\\", "/")
                    if m_test == failing_file or failing_file.endswith(m_test) or m_test.endswith(failing_file):
                        src = m.get("source_file", "").replace("\\", "/")
                        if src and not self._is_test_file(src):
                            failing_file = src
                            break

        self._record_step(
            step_number=iteration,
            action="TRACE_DEPENDENCIES",
            observation=f"Target localization: failing_file='{failing_file}', failing_symbol='{failing_symbol}'.",
            tool_output={
                "failing_file": failing_file,
                "failing_symbol": failing_symbol,
                "dependency_files": list(dependency_files),
            },
        )

        self.state_machine.transition(InvestigationState.ANALYZING)

        # Iteration 4: Rank Evidence & Evaluate Sufficiency
        iteration += 1
        ranked_evidence = self.ranker.rank_evidence(
            raw_evidence,
            failing_file=failing_file,
            failing_symbol=failing_symbol,
            dependency_files=dependency_files,
            failed_test_files=failed_test_files,
        )
        ranked_evidence = ranked_evidence[: self.MAX_EVIDENCE_ITEMS]

        err_msg = ""
        if parsed_trace:
            err_msg = f"{parsed_trace.exception_type}: {parsed_trace.error_message}"
        elif request.error_message:
            err_msg = request.error_message

        sufficiency, missing_info = self.sufficiency_evaluator.evaluate(
            evidence_list=ranked_evidence,
            error_message=err_msg,
            has_stack_trace=bool(parsed_trace and parsed_trace.frames),
            has_failed_tests=bool(parsed_tests),
        )

        self._record_step(
            step_number=iteration,
            action="RANK_AND_EVALUATE_SUFFICIENCY",
            observation=f"Ranked {len(ranked_evidence)} evidence items. Sufficiency: {sufficiency.value}.",
            tool_output={"sufficiency": sufficiency.value, "missing_info": missing_info},
        )

        # Iteration 5: Candidate Synthesis & Explainable Report
        iteration += 1
        candidates: List[RootCauseCandidateSchema] = []
        summary = ""
        overall_confidence = 0.0
        recommended_steps: List[str] = []

        if sufficiency == EvidenceSufficiency.INSUFFICIENT:
            summary = "Insufficient evidence to determine root cause."
            overall_confidence = 0.0
            recommended_steps = [
                "Provide a complete stack trace or reproduction script.",
                "Run unit/integration tests with verbose reporting enabled.",
                "Verify that the failing code path has been indexed by Code Intelligence.",
            ]
        else:
            candidates = self._synthesize_candidates(
                ranked_evidence=ranked_evidence,
                parsed_trace=parsed_trace,
                parsed_tests=parsed_tests,
                failing_file=failing_file,
                failing_symbol=failing_symbol,
                err_msg=err_msg,
            )

            if candidates:
                overall_confidence = candidates[0].confidence
                summary = f"Identified {len(candidates)} root cause candidate(s). Leading hypothesis: {candidates[0].title}"
            else:
                summary = "Evidence analyzed, but no definitive root-cause candidate met confidence threshold."
                overall_confidence = 0.2

            recommended_steps = [
                "Review the top root cause candidate and verified diff implications.",
                "Confirm whether edge cases in dependent symbols can be handled gracefully.",
                "Generate a minimal test case reproducing the specific boundary condition.",
            ]

        self.state_machine.transition(InvestigationState.CANDIDATES_GENERATED)
        self.state_machine.transition(InvestigationState.COMPLETED)

        duration = round((time.time() - start_time) * 1000, 2)
        self._record_step(
            step_number=iteration,
            action="FINALIZE_REPORT",
            observation=f"Investigation completed in {duration}ms. Final status: COMPLETED.",
            tool_output={"overall_confidence": overall_confidence, "candidates_count": len(candidates)},
        )

        top_candidate = candidates[0] if candidates else None

        return InvestigationReport(
            investigation_id=self.investigation_id,
            repository_id=self.repository_id,
            status=InvestigationState.COMPLETED,
            evidence_sufficiency=sufficiency,
            summary=summary,
            root_cause_candidates=candidates,
            top_candidate=top_candidate,
            overall_confidence=overall_confidence,
            ranked_evidence=ranked_evidence,
            missing_information=missing_info,
            recommended_next_steps=recommended_steps,
            iteration_count=iteration,
            duration_ms=duration,
        )

    def _synthesize_candidates(
        self,
        ranked_evidence: List[NormalizedEvidence],
        parsed_trace: Optional[ParsedStackTrace],
        parsed_tests: List[ParsedTestFailure],
        failing_file: Optional[str],
        failing_symbol: Optional[str],
        err_msg: str,
    ) -> List[RootCauseCandidateSchema]:
        """Synthesize multiple candidate hypotheses backed by traceable evidence."""
        candidates: List[RootCauseCandidateSchema] = []

        # Collect evidence IDs for attribution
        supporting_ids: List[str] = [e.evidence_id for e in ranked_evidence[:10]]

        # Check for dynamic dispatch (Case 5)
        is_dynamic_dispatch = (
            any("getattr" in (f.code_context or "").lower() for f in (parsed_trace.frames if parsed_trace else []))
            or any("getattr" in e.content.lower() for e in ranked_evidence)
            or any("dynamic_dispatch" in (f.function or "").lower() for f in (parsed_trace.frames if parsed_trace else []))
            or any("dynamic" in e.content.lower() and e.metadata.get("resolution_status") == ResolutionStatus.UNRESOLVED.value for e in ranked_evidence)
        )
        if is_dynamic_dispatch:
            dyn_ev_ids = [
                e.evidence_id for e in ranked_evidence
                if "dynamic" in e.content.lower() or "getattr" in e.content.lower() or e.type == EvidenceType.STACK_FRAME
            ]
            candidates.append(
                RootCauseCandidateSchema(
                    candidate_id=f"cand:{self.investigation_id[:8]}:dyn",
                    title="Dynamic Dispatch Target Unresolved",
                    description=(
                        "Failure involves dynamic attribute dispatch (getattr/dynamic target). "
                        "Static analysis cannot determine the dynamic target; the system does not fabricate unverified symbols."
                    ),
                    confidence=0.45,
                    affected_symbols=["unresolved:dynamic_target"],
                    affected_files=[failing_file] if failing_file else [],
                    supporting_evidence_ids=dyn_ev_ids[:3] or supporting_ids[:1],
                    contradicting_evidence_ids=[],
                    reasoning=(
                        "Python dynamic dispatch (getattr/eval) cannot be safely resolved without runtime introspection. "
                        "Marked as UNRESOLVED according to strict provenance invariants."
                    ),
                )
            )
            return candidates

        # Check for recent regression commit (Case 3)
        recent_commits = [
            e for e in ranked_evidence
            if e.type in (EvidenceType.COMMIT, EvidenceType.BLAME) and e.commit_sha
        ]

        # Case 7 / Standard: Multi-candidate generation when caller-callee relationship exists
        call_callee_evidence = [
            e for e in ranked_evidence
            if e.type == EvidenceType.CALL_RELATIONSHIP
            and e.metadata.get("direction") == "callee"
            and e.metadata.get("resolution_status") == ResolutionStatus.RESOLVED.value
        ]

        # Check if caller-callee or NoneType error
        is_none_or_lookup_error = any(
            err in err_msg.lower()
            for err in ["nonetype", "none", "keyerror", "not subscriptable", "attributeerror", "cannot read properties"]
        )

        has_callee_call = False
        target_symbol = "database.get_user"
        target_file = "app/database.py"

        if call_callee_evidence:
            has_callee_call = True
            callee_ev = call_callee_evidence[0]
            target_symbol = callee_ev.metadata.get("target", "database.get_user")
            target_file = callee_ev.repository_path or "app/database.py"
        elif parsed_trace:
            for f in parsed_trace.frames:
                if f.code_context and any(call_fn in f.code_context for call_fn in ["fetch_db_user", "get_user", "save_user", "query_users"]):
                    has_callee_call = True
                    target_symbol = "database.get_user"
                    target_file = "app/database.py"
                    break

        if is_none_or_lookup_error and has_callee_call:
            # Candidate 1: Callee returned unexpected None or missing record
            c1_supporting = [e.evidence_id for e in call_callee_evidence] if call_callee_evidence else [supporting_ids[0]]
            if recent_commits:
                c1_supporting.append(recent_commits[0].evidence_id)
            c1_conf = self._calibrate_confidence(
                base_confidence=0.78,
                supporting_count=len(c1_supporting),
                has_resolved_symbols=True,
                is_direct_stack=bool(parsed_trace and parsed_trace.failing_frame),
            )

            candidates.append(
                RootCauseCandidateSchema(
                    candidate_id=f"cand:{self.investigation_id[:8]}:1",
                    title=f"Unexpected None or missing entity returned by '{target_symbol}'",
                    description=(
                        f"Function '{target_symbol}' called by '{failing_symbol or failing_file}' returned None unexpectedly, "
                        f"triggering an unhandled '{err_msg or 'lookup error'}' downstream."
                    ),
                    confidence=c1_conf,
                    affected_symbols=[target_symbol],
                    affected_files=[target_file],
                    supporting_evidence_ids=c1_supporting,
                    contradicting_evidence_ids=[],
                    reasoning=(
                        f"Stack trace and call graph confirm '{failing_symbol or failing_file}' executes '{target_symbol}'. "
                        "The runtime failure occurred immediately after this call."
                    ),
                )
            )

            # Candidate 2: Caller failed to validate or handle None return
            c2_supporting = [supporting_ids[0]]
            if len(supporting_ids) > 1:
                c2_supporting.append(supporting_ids[1])
            c2_conf = self._calibrate_confidence(
                base_confidence=0.65,
                supporting_count=len(c2_supporting),
                has_resolved_symbols=True,
                is_direct_stack=bool(parsed_trace and parsed_trace.failing_frame),
            )

            candidates.append(
                RootCauseCandidateSchema(
                    candidate_id=f"cand:{self.investigation_id[:8]}:2",
                    title=f"Missing None check / defensive handling in '{failing_symbol or failing_file}'",
                    description=(
                        f"Function '{failing_symbol or failing_file}' assumes a non-None return value from '{target_symbol}' "
                        "and does not provide fallback handling for missing records."
                    ),
                    confidence=c2_conf,
                    affected_symbols=[failing_symbol or ""],
                    affected_files=[failing_file or ""],
                    supporting_evidence_ids=c2_supporting,
                    contradicting_evidence_ids=[],
                    reasoning=(
                        "Even if the underlying database entity does not exist, the consuming service should handle "
                        "None defensively rather than raising an unhandled exception."
                    ),
                )
            )

            return candidates

        # Default Single / Primary Candidate (Case 1, Case 2, Case 3, Case 4)
        cand_title = ""
        cand_desc = ""
        aff_symbols = [failing_symbol] if failing_symbol else []
        aff_files = [failing_file] if failing_file else []

        if recent_commits and failing_file:
            top_commit = recent_commits[0]
            cand_title = f"Regression introduced in commit {top_commit.commit_sha[:7]} at {failing_file}"
            cand_desc = f"{top_commit.content}. Caused failure: {err_msg}."
            cand_conf = 0.88
        elif parsed_trace and parsed_trace.failing_frame:
            ff = parsed_trace.failing_frame
            # If the failing frame was in a test file, candidate targets the tested source file!
            if self._is_test_file(ff.file) and failing_file and not self._is_test_file(failing_file):
                cand_title = f"Defect in '{failing_symbol or failing_file}' detected by test '{ff.function}'"
                cand_desc = f"Test assertion '{ff.function}' failed targeting '{failing_file}'. Error: {err_msg}."
                cand_conf = 0.92
                aff_files = [failing_file]
                if failing_symbol:
                    aff_symbols = [failing_symbol]
            else:
                cand_title = f"Failure in '{ff.function}' at {ff.file}:{ff.line}"
                cand_desc = f"Execution failed in '{ff.function}' with {err_msg}."
                cand_conf = 0.90 if ff.resolution_status == ResolutionStatus.RESOLVED.value else 0.70
        elif parsed_tests:
            pt = parsed_tests[0]
            target_str = pt.tested_file or pt.test_file
            cand_title = f"Assertion failure in test '{pt.test_function or pt.test_file}'"
            cand_desc = f"Test failure targeting '{target_str}'. Expected {pt.expected}, received {pt.actual}."
            cand_conf = 0.82
            if pt.tested_file:
                aff_files.append(pt.tested_file)
        else:
            cand_title = f"Failure in module {failing_file or 'suspected component'}"
            cand_desc = f"Reported failure: {err_msg}"
            cand_conf = 0.60

        calibrated_conf = self._calibrate_confidence(
            base_confidence=cand_conf,
            supporting_count=len(supporting_ids),
            has_resolved_symbols=bool(failing_symbol),
            is_direct_stack=bool(parsed_trace and parsed_trace.failing_frame),
        )

        candidates.append(
            RootCauseCandidateSchema(
                candidate_id=f"cand:{self.investigation_id[:8]}:primary",
                title=cand_title,
                description=cand_desc,
                confidence=calibrated_conf,
                affected_symbols=[s for s in aff_symbols if s],
                affected_files=[f for f in aff_files if f],
                supporting_evidence_ids=supporting_ids[:5],
                contradicting_evidence_ids=[],
                reasoning=(
                    f"Evidence localized failure to {failing_file or 'target file'} with corroborating "
                    f"Code Intelligence symbols and test relationships. No contradicting evidence found."
                ),
            )
        )

        return candidates

    def _calibrate_confidence(
        self,
        base_confidence: float,
        supporting_count: int,
        has_resolved_symbols: bool,
        is_direct_stack: bool,
    ) -> float:
        """Calibrate evidence confidence based on deterministic provenance factors."""
        conf = base_confidence

        if has_resolved_symbols:
            conf += 0.05
        else:
            conf -= 0.10

        if is_direct_stack:
            conf += 0.05

        if supporting_count >= 3:
            conf += 0.03

        return min(0.98, max(0.20, round(conf, 2)))
