"""Deterministic Test Failure Parser.

Extracts test failures, assertion mismatches, expected vs actual values,
and maps failed tests to source code components via Code Intelligence relationships.
"""

import re
from typing import Any, Dict, List, Optional, Union
from agent.models import ParsedTestFailure
from code_intelligence.tests.test_relationships import TestRelationshipsEngine


class TestFailureParser:
    """Parses test failure items and connects them to tested source components."""

    PYTEST_NODE_RE = re.compile(
        r'^(?P<file>[^:]+)::(?:(?P<class>[^:]+)::)?(?P<func>[^:\s]+)(?:\s+(?P<outcome>FAILED|ERROR))?'
    )

    def parse_item(self, item: Union[str, Dict[str, Any]]) -> ParsedTestFailure:
        """Parse a single test failure record from string or dictionary."""
        if isinstance(item, dict):
            return ParsedTestFailure(
                test_file=item.get("test_file", "").replace("\\", "/"),
                test_function=item.get("test_function", ""),
                assertion=item.get("assertion"),
                expected=str(item.get("expected")) if item.get("expected") is not None else None,
                actual=str(item.get("actual")) if item.get("actual") is not None else None,
                exception=item.get("exception"),
                stack_trace=item.get("stack_trace"),
                tested_symbol_id=item.get("tested_symbol_id"),
                tested_file=item.get("tested_file"),
                confidence=float(item.get("confidence", 1.0)),
            )

        # String format: e.g. "tests/test_service.py::test_user_process FAILED"
        raw_str = str(item).strip()
        match = self.PYTEST_NODE_RE.match(raw_str)
        if match:
            test_file = match.group("file").replace("\\", "/")
            test_func = match.group("func")
            return ParsedTestFailure(
                test_file=test_file,
                test_function=test_func,
                confidence=1.0,
            )

        # Simple file or symbol string
        parts = raw_str.split("::")
        if len(parts) >= 2:
            return ParsedTestFailure(
                test_file=parts[0].replace("\\", "/"),
                test_function=parts[1],
                confidence=1.0,
            )

        return ParsedTestFailure(
            test_file=raw_str.replace("\\", "/"),
            test_function="",
            confidence=0.5,
        )

    def map_to_source(
        self,
        failure: ParsedTestFailure,
        test_engine: Optional[TestRelationshipsEngine] = None,
        test_mappings: Optional[List[Dict[str, Any]]] = None,
    ) -> ParsedTestFailure:
        """Map failed test to target implementation file and symbol using Code Intelligence."""
        if not test_mappings:
            return failure

        norm_test_file = failure.test_file.replace("\\", "/")
        matching_mappings = [
            m for m in test_mappings
            if m.get("test_file", "").replace("\\", "/").endswith(norm_test_file)
            or norm_test_file.endswith(m.get("test_file", "").replace("\\", "/"))
        ]

        if not matching_mappings:
            return failure

        best_match = max(matching_mappings, key=lambda m: m.get("confidence", 0.0))
        failure.tested_file = best_match.get("source_file", "").replace("\\", "/")
        failure.confidence = float(best_match.get("confidence", 0.8))

        # Check if function matches a specific symbol
        if failure.test_function:
            clean_func = failure.test_function.lower().replace("test_", "").replace("_test", "")
            for m in matching_mappings:
                if clean_func in m.get("source_file", "").lower():
                    failure.tested_file = m.get("source_file", "").replace("\\", "/")
                    failure.confidence = float(m.get("confidence", 0.8))
                    break

        return failure
