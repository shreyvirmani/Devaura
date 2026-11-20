"""Evidence Collector Layer.

Gathers structured evidence from Code Intelligence, Git Intelligence,
Stack Trace Analysis, Test Failures, and Native MCP Tools.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from agent.models import (
    EvidenceSource,
    EvidenceType,
    InvestigationRequest,
    NormalizedEvidence,
    ParsedStackFrame,
    ParsedStackTrace,
    ParsedTestFailure,
    ResolutionStatus,
)
from agent.parsers.stack_trace_parser import StackTraceParser
from agent.parsers.test_failure_parser import TestFailureParser
from code_intelligence.git.git_intelligence import GitIntelligence
from code_intelligence.graph.queries import GraphQueryEngine
from code_intelligence.graph.relationship_builder import RelationshipBuilder
from code_intelligence.indexer.file_indexer import FileIndexer
from code_intelligence.search import MultiTierSearchCoordinator
from code_intelligence.tests.test_relationships import TestRelationshipsEngine
from mcp.policy import policy_engine


class EvidenceCollector:
    """Coordinates evidence collection across repository code intelligence and git history."""

    def __init__(
        self,
        workspace_root: str,
        investigation_id: str,
        repository_id: str = "default-repo",
    ):
        self.workspace_root = workspace_root
        self.investigation_id = investigation_id
        self.repository_id = repository_id

        self.stack_parser = StackTraceParser()
        self.test_parser = TestFailureParser()
        self.file_indexer = FileIndexer(workspace_root=workspace_root)
        self.git_intel = GitIntelligence()
        self.search_coord = MultiTierSearchCoordinator(workspace_root=workspace_root)

        self._ev_counter = 0

    def _next_evidence_id(self) -> str:
        self._ev_counter += 1
        return f"ev:{self.investigation_id[:8]}:{self._ev_counter}"

    def collect_all_evidence(
        self,
        request: InvestigationRequest,
    ) -> Tuple[List[NormalizedEvidence], Optional[ParsedStackTrace], List[ParsedTestFailure]]:
        """Execute full evidence collection pipeline based on investigation request."""
        evidence_list: List[NormalizedEvidence] = []

        # Index repository files in workspace to obtain AST symbols
        parsed_files = self.file_indexer.index_workspace()
        builder = RelationshipBuilder(repository_id=self.repository_id)
        repo_graph = builder.build_graph(parsed_files)
        query_engine = GraphQueryEngine(repo_graph)

        test_engine = TestRelationshipsEngine(workspace_root=self.workspace_root)
        test_mappings = test_engine.discover_test_mappings(parsed_files)

        # 1. Parse and Collect Stack Trace Evidence
        parsed_trace: Optional[ParsedStackTrace] = None
        failing_file: Optional[str] = None
        failing_symbol: Optional[str] = None

        if request.stack_trace:
            parsed_trace = self.stack_parser.parse(
                request.stack_trace, workspace_root=self.workspace_root
            )

            # Record Error message evidence
            if parsed_trace.error_message:
                evidence_list.append(
                    NormalizedEvidence(
                        evidence_id=self._next_evidence_id(),
                        investigation_id=self.investigation_id,
                        source=EvidenceSource.STACK_TRACE,
                        type=EvidenceType.ERROR_MESSAGE,
                        content=f"{parsed_trace.exception_type}: {parsed_trace.error_message}",
                        confidence=1.0,
                        relevance=0.90,
                        metadata={"exception_type": parsed_trace.exception_type},
                    )
                )

            # Map stack frames to Code Intelligence symbols
            for idx, frame in enumerate(parsed_trace.frames):
                mapped_sym_id, res_status = self._resolve_frame_symbol(frame, parsed_files)
                frame.symbol_id = mapped_sym_id
                frame.resolution_status = res_status

                is_top = (idx == len(parsed_trace.frames) - 1)
                relevance = 1.0 if is_top else 0.75

                ev_content = f"Stack frame #{idx + 1}: {frame.file}:{frame.line} in {frame.function}"
                if frame.code_context:
                    ev_content += f" -> {frame.code_context}"

                evidence_list.append(
                    NormalizedEvidence(
                        evidence_id=self._next_evidence_id(),
                        investigation_id=self.investigation_id,
                        source=EvidenceSource.STACK_TRACE,
                        type=EvidenceType.STACK_FRAME,
                        content=ev_content,
                        repository_path=frame.file,
                        symbol_id=mapped_sym_id,
                        line_start=frame.line,
                        line_end=frame.line,
                        confidence=1.0 if res_status == ResolutionStatus.RESOLVED.value else 0.85,
                        relevance=relevance,
                        metadata={
                            "frame_index": idx,
                            "is_application_code": frame.is_application_code,
                            "resolution_status": res_status,
                            "function": frame.function,
                        },
                    )
                )

            if parsed_trace.failing_frame:
                failing_file = parsed_trace.failing_frame.file
                failing_symbol = parsed_trace.failing_frame.symbol_id

        # If error message provided separately
        elif request.error_message:
            evidence_list.append(
                NormalizedEvidence(
                    evidence_id=self._next_evidence_id(),
                    investigation_id=self.investigation_id,
                    source=EvidenceSource.USER_REPORT,
                    type=EvidenceType.ERROR_MESSAGE,
                    content=request.error_message,
                    confidence=0.8,
                    relevance=0.6,
                )
            )

        # 2. Parse and Collect Failed Tests Evidence
        parsed_tests: List[ParsedTestFailure] = []
        if request.failed_tests:
            for item in request.failed_tests:
                tf = self.test_parser.parse_item(item)
                tf = self.test_parser.map_to_source(tf, test_mappings=test_mappings)
                parsed_tests.append(tf)

                if not failing_file and tf.tested_file:
                    failing_file = tf.tested_file

                test_content = f"Failed Test: {tf.test_file}"
                if tf.test_function:
                    test_content += f"::{tf.test_function}"
                if tf.assertion:
                    test_content += f" | Assertion: {tf.assertion}"
                if tf.expected and tf.actual:
                    test_content += f" (expected {tf.expected}, got {tf.actual})"

                evidence_list.append(
                    NormalizedEvidence(
                        evidence_id=self._next_evidence_id(),
                        investigation_id=self.investigation_id,
                        source=EvidenceSource.TEST,
                        type=EvidenceType.TEST_FAILURE,
                        content=test_content,
                        repository_path=tf.test_file,
                        confidence=tf.confidence,
                        relevance=0.90,
                        metadata={
                            "test_function": tf.test_function,
                            "tested_file": tf.tested_file,
                            "expected": tf.expected,
                            "actual": tf.actual,
                            "resolution_status": ResolutionStatus.RESOLVED.value if tf.tested_file else ResolutionStatus.UNRESOLVED.value,
                        },
                    )
                )

        # 3. Collect Code Intelligence Graph Relationships (Callers, Callees, Tests)
        if failing_symbol or failing_file:
            # Add Symbol definition evidence
            target_symbols = self._find_symbols_for_target(failing_file, failing_symbol, parsed_files)
            for sym in target_symbols:
                evidence_list.append(
                    NormalizedEvidence(
                        evidence_id=self._next_evidence_id(),
                        investigation_id=self.investigation_id,
                        source=EvidenceSource.CODE_INTELLIGENCE,
                        type=EvidenceType.SYMBOL,
                        content=f"Symbol '{sym['name']}' ({sym['kind']}) defined at {sym['file_path']}:{sym['start_line']}-{sym['end_line']}",
                        repository_path=sym["file_path"],
                        symbol_id=sym["id"],
                        line_start=sym["start_line"],
                        line_end=sym["end_line"],
                        confidence=1.0,
                        relevance=0.85,
                        metadata={"kind": sym["kind"], "signature": sym["signature"]},
                    )
                )

                # Query callers and callees
                callees = query_engine.get_callees(sym["id"])
                for edge, target_node in callees:
                    evidence_list.append(
                        NormalizedEvidence(
                            evidence_id=self._next_evidence_id(),
                            investigation_id=self.investigation_id,
                            source=EvidenceSource.CODE_INTELLIGENCE,
                            type=EvidenceType.CALL_RELATIONSHIP,
                            content=f"Function '{sym['name']}' calls '{target_node.label}' ({edge.evidence})",
                            repository_path=sym["file_path"],
                            symbol_id=target_node.id,
                            confidence=edge.confidence,
                            relevance=0.80,
                            metadata={
                                "resolution_status": edge.resolution_status,
                                "direction": "callee",
                                "target": target_node.label,
                            },
                        )
                    )

                callers = query_engine.get_callers(sym["id"])
                for edge, src_node in callers:
                    evidence_list.append(
                        NormalizedEvidence(
                            evidence_id=self._next_evidence_id(),
                            investigation_id=self.investigation_id,
                            source=EvidenceSource.CODE_INTELLIGENCE,
                            type=EvidenceType.CALL_RELATIONSHIP,
                            content=f"Function '{sym['name']}' is called by '{src_node.label}' ({edge.evidence})",
                            repository_path=sym["file_path"],
                            symbol_id=src_node.id,
                            confidence=edge.confidence,
                            relevance=0.75,
                            metadata={
                                "resolution_status": edge.resolution_status,
                                "direction": "caller",
                                "caller": src_node.label,
                            },
                        )
                    )

        # Connect related tests from test mappings
        if failing_file:
            norm_ff = failing_file.replace("\\", "/")
            for tm in test_mappings:
                tm_src = tm.get("source_file", "").replace("\\", "/")
                if norm_ff.endswith(tm_src) or tm_src.endswith(norm_ff):
                    evidence_list.append(
                        NormalizedEvidence(
                            evidence_id=self._next_evidence_id(),
                            investigation_id=self.investigation_id,
                            source=EvidenceSource.CODE_INTELLIGENCE,
                            type=EvidenceType.TEST_RELATIONSHIP,
                            content=f"Test '{tm.get('test_file')}' targets '{tm.get('source_file')}' ({tm.get('evidence')})",
                            repository_path=tm.get("test_file"),
                            confidence=float(tm.get("confidence", 0.8)),
                            relevance=0.70,
                            metadata={
                                "evidence": tm.get("evidence"),
                                "test_file": tm.get("test_file"),
                                "source_file": tm.get("source_file"),
                            },
                        )
                    )

        # 4. Collect Git Evidence (Commits, Blame, Co-change)
        if failing_file and Path(self.workspace_root, ".git").exists():
            # Recent commits touching failing file
            commits = self.git_intel.get_commit_history(
                self.workspace_root, file_path=failing_file, max_count=5
            )
            for idx, c in enumerate(commits):
                is_recent = (idx == 0)
                evidence_list.append(
                    NormalizedEvidence(
                        evidence_id=self._next_evidence_id(),
                        investigation_id=self.investigation_id,
                        source=EvidenceSource.GIT,
                        type=EvidenceType.COMMIT,
                        content=f"Commit {c.get('sha', '')[:7]} by {c.get('author', '')}: {c.get('message', '')}",
                        repository_path=failing_file,
                        commit_sha=c.get("sha"),
                        confidence=1.0,
                        relevance=0.75 if is_recent else 0.50,
                        metadata={
                            "commit_distance": idx,
                            "date": c.get("date"),
                            "author": c.get("author"),
                        },
                    )
                )

            # Blame on failing line if known
            if parsed_trace and parsed_trace.failing_frame:
                line_no = parsed_trace.failing_frame.line
                blame_lines = self.git_intel.get_file_blame(
                    self.workspace_root, failing_file, start_line=line_no, end_line=line_no
                )
                if blame_lines:
                    b = blame_lines[0]
                    evidence_list.append(
                        NormalizedEvidence(
                            evidence_id=self._next_evidence_id(),
                            investigation_id=self.investigation_id,
                            source=EvidenceSource.GIT,
                            type=EvidenceType.BLAME,
                            content=f"Line {line_no} modified in commit {b.get('commit_sha', '')[:7]} by {b.get('author', '')}: {b.get('line_content', '')}",
                            repository_path=failing_file,
                            commit_sha=b.get("commit_sha"),
                            line_start=line_no,
                            line_end=line_no,
                            confidence=1.0,
                            relevance=0.75,
                            metadata={"author": b.get("author"), "date": b.get("date")},
                        )
                    )

            # Co-change correlation
            co_changes = self.git_intel.get_change_co_occurrence(self.workspace_root, failing_file)
            for cc in co_changes[:3]:
                evidence_list.append(
                    NormalizedEvidence(
                        evidence_id=self._next_evidence_id(),
                        investigation_id=self.investigation_id,
                        source=EvidenceSource.GIT,
                        type=EvidenceType.CODE_CHANGE,
                        content=f"File '{cc.get('co_changed_file')}' co-changes with '{failing_file}' ({cc.get('co_occurrences')} times, score {cc.get('score')})",
                        repository_path=cc.get("co_changed_file"),
                        confidence=float(cc.get("score", 0.5)),
                        relevance=0.35,
                        metadata={
                            "is_co_occurrence": True,
                            "co_occurrences": cc.get("co_occurrences"),
                            "disclaimer": "Git co-change represents historical commit correlation, not structural code dependency.",
                        },
                    )
                )

        return evidence_list, parsed_trace, parsed_tests

    def _resolve_frame_symbol(
        self,
        frame: ParsedStackFrame,
        parsed_files: List[Any],
    ) -> Tuple[Optional[str], str]:
        """Match a stack frame to a concrete Code Intelligence symbol without fabricating entities."""
        norm_frame_file = frame.file.replace("\\", "/")

        for pf in parsed_files:
            norm_pf_path = pf.path.replace("\\", "/")
            if norm_pf_path.endswith(norm_frame_file) or norm_frame_file.endswith(norm_pf_path):
                # 1. Match by exact function name first (including methods)
                for sym in pf.symbols:
                    sym_id = f"symbol:{norm_pf_path}:{sym.qualified_name}"
                    if frame.function and (frame.function == sym.name or sym.qualified_name.endswith("." + frame.function)):
                        return sym_id, ResolutionStatus.RESOLVED.value

                # 2. Match by line range picking innermost symbol (smallest span)
                matching_symbols = [
                    sym for sym in pf.symbols if sym.start_line <= frame.line <= sym.end_line
                ]
                if matching_symbols:
                    innermost = min(matching_symbols, key=lambda s: (s.end_line - s.start_line))
                    sym_id = f"symbol:{norm_pf_path}:{innermost.qualified_name}"
                    return sym_id, ResolutionStatus.RESOLVED.value

                return None, ResolutionStatus.PARTIALLY_RESOLVED.value

        return None, ResolutionStatus.UNRESOLVED.value

    def _find_symbols_for_target(
        self,
        failing_file: Optional[str],
        failing_symbol: Optional[str],
        parsed_files: List[Any],
    ) -> List[Dict[str, Any]]:
        """Find matching AST symbols for a suspected target."""
        matched: List[Dict[str, Any]] = []
        if failing_symbol:
            for pf in parsed_files:
                norm_pf_path = pf.path.replace("\\", "/")
                for sym in pf.symbols:
                    sym_id = f"symbol:{norm_pf_path}:{sym.qualified_name}"
                    if sym_id == failing_symbol or failing_symbol in sym_id:
                        kind_val = sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind)
                        matched.append({
                            "id": sym_id,
                            "name": sym.name,
                            "file_path": norm_pf_path,
                            "start_line": sym.start_line,
                            "end_line": sym.end_line,
                            "kind": kind_val,
                            "signature": sym.signature,
                        })
            if matched:
                return matched

        if failing_file:
            norm_ff = failing_file.replace("\\", "/")
            for pf in parsed_files:
                norm_pf_path = pf.path.replace("\\", "/")
                if norm_pf_path.endswith(norm_ff) or norm_ff.endswith(norm_pf_path):
                    for sym in pf.symbols[:3]:
                        sym_id = f"symbol:{norm_pf_path}:{sym.qualified_name}"
                        kind_val = sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind)
                        matched.append({
                            "id": sym_id,
                            "name": sym.name,
                            "file_path": norm_pf_path,
                            "start_line": sym.start_line,
                            "end_line": sym.end_line,
                            "kind": kind_val,
                            "signature": sym.signature,
                        })

        return matched
