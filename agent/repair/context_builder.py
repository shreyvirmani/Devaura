"""Repair Context Builder.

Validates Phase 4 investigation output and transforms it into a structured,
immutable RepairContext contract for the Repair Planner.
"""

import os
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from agent.models import EvidenceSufficiency, InvestigationReport
from agent.repair.models import RepairContext
from database.models import Investigation, RootCauseCandidate


class RepairContextBuilder:
    """Builds and validates RepairContext from investigation findings."""

    MAX_ALLOWED_AFFECTED_FILES = 5
    DISALLOWED_FILE_PATTERNS = [
        ".env",
        "id_rsa",
        ".pem",
        ".key",
        "credentials",
        "secrets",
        ".git",
    ]

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def validate_and_build(
        self,
        investigation: Union[Investigation, InvestigationReport, Dict[str, Any]],
        selected_candidate_id: Optional[str] = None,
        repair_id: Optional[str] = None,
        db_session: Any = None,
    ) -> Tuple[bool, Optional[RepairContext], Optional[str]]:
        """Validate investigation state and evidence, then construct RepairContext.

        Returns:
            Tuple of (is_valid, RepairContext or None, error_message or None).
        """
        repair_id = repair_id or str(uuid.uuid4())

        # 1. Extract investigation attributes
        if isinstance(investigation, Investigation):
            inv_id = investigation.id
            repo_id = investigation.repository_id
            status = str(investigation.status)
            sufficiency = str(investigation.evidence_sufficiency)
            failure_dict = {
                "failure_type": investigation.failure_type,
                "error_message": investigation.error_message or "",
                "stack_trace": investigation.stack_trace or "",
                "failed_tests": investigation.failed_tests or [],
            }
            candidates = [
                {
                    "candidate_id": getattr(c, "candidate_id", None) or getattr(c, "id", None) or str(uuid.uuid4()),
                    "title": c.title,
                    "description": c.description,
                    "confidence": c.confidence,
                    "affected_symbols": c.affected_symbols or [],
                    "affected_files": c.affected_files or [],
                    "supporting_evidence_ids": c.supporting_evidence_ids or [],
                    "contradicting_evidence_ids": c.contradicting_evidence_ids or [],
                    "reasoning": c.reasoning or "",
                }
                for c in investigation.root_cause_candidates
            ]
            evidence_items = [
                {
                    "evidence_id": e.id,
                    "source": e.source,
                    "type": e.type,
                    "content": e.content,
                    "repository_path": e.repository_path,
                    "symbol_id": e.symbol_id,
                    "line_start": e.line_start,
                    "line_end": e.line_end,
                    "confidence": e.confidence,
                    "metadata": e.metadata_json or {},
                }
                for e in investigation.evidence_items
            ]
        elif isinstance(investigation, InvestigationReport):
            inv_id = investigation.investigation_id
            repo_id = investigation.repository_id
            status = investigation.status.value if hasattr(investigation.status, "value") else str(investigation.status)
            sufficiency = (
                investigation.evidence_sufficiency.value
                if hasattr(investigation.evidence_sufficiency, "value")
                else str(investigation.evidence_sufficiency)
            )
            failure_dict = {
                "failure_type": "UNKNOWN",
                "error_message": investigation.summary,
                "stack_trace": "",
                "failed_tests": [],
            }
            candidates = [
                {
                    "candidate_id": getattr(c, "candidate_id", None) or getattr(c, "id", None) or str(uuid.uuid4()),
                    "title": c.title,
                    "description": c.description,
                    "confidence": c.confidence,
                    "affected_symbols": c.affected_symbols,
                    "affected_files": c.affected_files,
                    "supporting_evidence_ids": c.supporting_evidence_ids,
                    "contradicting_evidence_ids": c.contradicting_evidence_ids,
                    "reasoning": c.reasoning,
                }
                for c in investigation.root_cause_candidates
            ]
            evidence_items = [
                {
                    "evidence_id": e.evidence_id,
                    "source": e.source.value if hasattr(e.source, "value") else str(e.source),
                    "type": e.type.value if hasattr(e.type, "value") else str(e.type),
                    "content": e.content,
                    "repository_path": e.repository_path,
                    "symbol_id": e.symbol_id,
                    "line_start": e.line_start,
                    "line_end": e.line_end,
                    "confidence": e.confidence,
                    "metadata": e.metadata or {},
                }
                for e in investigation.ranked_evidence
            ]
        else:
            inv_id = investigation.get("investigation_id") or investigation.get("id") or str(uuid.uuid4())
            repo_id = investigation.get("repository_id", "default-repo")
            status = str(investigation.get("status", "COMPLETED"))
            sufficiency = str(investigation.get("evidence_sufficiency", "SUFFICIENT"))
            failure_dict = investigation.get("failure", {})
            candidates = investigation.get("root_cause_candidates", [])
            evidence_items = investigation.get("evidence_items") or investigation.get("ranked_evidence") or []

        # 2. Validation: Status Check
        valid_statuses = {"COMPLETED", "CANDIDATES_GENERATED", "EVIDENCE_READY"}
        if status not in valid_statuses:
            return (
                False,
                None,
                f"Investigation is in state '{status}', but repair requires one of {valid_statuses}.",
            )

        # 3. Validation: Evidence Sufficiency
        if sufficiency == EvidenceSufficiency.INSUFFICIENT.value or sufficiency == "INSUFFICIENT":
            return (
                False,
                None,
                "Evidence sufficiency is INSUFFICIENT. Cannot formulate safe repair plan without reliable root cause.",
            )

        # 4. Validation: Root Cause Candidates
        if not candidates:
            return (
                False,
                None,
                "No root cause candidates found in investigation.",
            )

        # Select candidate
        selected_cand = None
        if selected_candidate_id:
            for c in candidates:
                if c.get("candidate_id") == selected_candidate_id:
                    selected_cand = c
                    break
            if not selected_cand:
                return (
                    False,
                    None,
                    f"Specified root cause candidate '{selected_candidate_id}' not found.",
                )
        else:
            # Default to top candidate
            selected_cand = candidates[0]

        # 5. Validation: Supporting Evidence
        supporting_ids = set(selected_cand.get("supporting_evidence_ids", []))
        if not supporting_ids and not evidence_items:
            return (
                False,
                None,
                f"Root cause candidate '{selected_cand.get('candidate_id')}' has no supporting evidence.",
            )

        # Filter supporting evidence
        supporting_evidence = []
        if supporting_ids:
            supporting_evidence = [
                e for e in evidence_items if e.get("evidence_id") in supporting_ids
            ]
        if not supporting_evidence and evidence_items:
            # Fallback to top relevant evidence items
            supporting_evidence = evidence_items[:5]

        # 6. Validation: Affected Files
        affected_files = selected_cand.get("affected_files", [])
        if not affected_files:
            # Try to infer from supporting evidence repository_path
            for e in supporting_evidence:
                rp = e.get("repository_path")
                if rp and rp not in affected_files:
                    affected_files.append(rp)

        if not affected_files:
            return (
                False,
                None,
                "No affected files identified in root cause candidate or supporting evidence.",
            )

        if len(affected_files) > self.MAX_ALLOWED_AFFECTED_FILES:
            return (
                False,
                None,
                f"Repair scope exceeds maximum bound: {len(affected_files)} files affected (max: {self.MAX_ALLOWED_AFFECTED_FILES}).",
            )

        # Safety: Disallowed files or path traversal
        for f in affected_files:
            if ".." in f or os.path.isabs(f):
                return (
                    False,
                    None,
                    f"Path traversal or absolute path detected in affected file: '{f}'",
                )
            f_lower = f.lower()
            if any(pattern in f_lower for pattern in self.DISALLOWED_FILE_PATTERNS):
                return (
                    False,
                    None,
                    f"Sensitive or restricted file target in repair scope: '{f}'",
                )

        # 7. Extract Affected Lines & Related Tests
        affected_lines: Dict[str, List[int]] = {}
        for e in supporting_evidence:
            rp = e.get("repository_path")
            ls = e.get("line_start")
            le = e.get("line_end")
            if rp and ls:
                lines = affected_lines.setdefault(rp, [])
                lines.append(ls)
                if le and le != ls:
                    lines.append(le)

        # Infer related tests
        related_tests: List[str] = []
        for f in affected_files:
            base_name = os.path.basename(f)
            stem, _ = os.path.splitext(base_name)
            # Standard test filename heuristics
            possible_tests = [
                f"tests/test_{stem}.py",
                f"test_{stem}.py",
                f"tests/{stem}_test.py",
                f"__tests__/{stem}.test.ts",
                f"__tests__/{stem}.test.js",
                f"tests/{stem}.test.ts",
            ]
            for pt in possible_tests:
                if os.path.exists(os.path.join(self.workspace_root, pt)):
                    if pt not in related_tests:
                        related_tests.append(pt)

        # If failed tests were part of the failure dict, add them
        for ft in failure_dict.get("failed_tests", []):
            if isinstance(ft, str) and ft not in related_tests:
                related_tests.append(ft)
            elif isinstance(ft, dict) and "test_file" in ft:
                tf = ft["test_file"]
                if tf not in related_tests:
                    related_tests.append(tf)

        context = RepairContext(
            repair_id=repair_id,
            investigation_id=inv_id,
            repository_id=repo_id,
            repository_path=self.workspace_root,
            repository_revision="HEAD",
            failure=failure_dict,
            selected_root_cause=selected_cand,
            supporting_evidence=supporting_evidence,
            affected_files=affected_files,
            affected_symbols=selected_cand.get("affected_symbols", []),
            affected_lines=affected_lines,
            related_tests=related_tests,
            recent_changes=[],
            unresolved_evidence=[],
            forbidden_assumptions=[
                "Do not modify files outside designated affected_files",
                "Do not delete or alter external API signatures",
                "Do not introduce external dependencies",
            ],
            repair_scope={
                "max_files": self.MAX_ALLOWED_AFFECTED_FILES,
                "max_lines_changed": 100,
                "allowed_files": affected_files,
            },
            constraints=[
                "Deterministic and minimal patch",
                "Fix root cause without regressions",
                "Adhere to repository coding style",
            ],
        )

        return True, context, None
