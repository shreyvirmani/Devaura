"""Evidence Sufficiency Evaluator.

Classifies the collected investigation evidence into:
- SUFFICIENT: High-confidence evidence directly localizing failure origin.
- PARTIALLY_SUFFICIENT: Plausible clues or files, but missing direct test/trace or ambiguous.
- INSUFFICIENT: Only generic error messages or absence of resolvable source entities.

Crucial System Principle:
-------------------------
The system MUST be allowed to conclude:
"Insufficient evidence to determine root cause."
This is a required feature, not a failure.
"""

from typing import List, Tuple
from agent.models import EvidenceSufficiency, EvidenceType, NormalizedEvidence, ResolutionStatus


class EvidenceSufficiencyEvaluator:
    """Evaluates whether the collected evidence meets the threshold for root-cause diagnosis."""

    GENERIC_ERROR_PATTERNS = [
        "something went wrong",
        "unknown error",
        "internal server error",
        "an error occurred",
        "failed with error",
        "command failed",
        "operation failed",
    ]

    def evaluate(
        self,
        evidence_list: List[NormalizedEvidence],
        error_message: str = "",
        has_stack_trace: bool = False,
        has_failed_tests: bool = False,
    ) -> Tuple[EvidenceSufficiency, List[str]]:
        """Evaluate evidence and return (EvidenceSufficiency, missing_information_list)."""
        missing_info: List[str] = []

        if not evidence_list:
            missing_info.append("No evidence items were collected from repository or logs.")
            return EvidenceSufficiency.INSUFFICIENT, missing_info

        # Check for generic error message with nothing else
        is_generic_msg = False
        if error_message:
            clean_msg = error_message.lower().strip()
            if any(p in clean_msg for p in self.GENERIC_ERROR_PATTERNS) and len(clean_msg) < 50:
                is_generic_msg = True

        # Check evidence categories
        stack_frame_items = [e for e in evidence_list if e.type == EvidenceType.STACK_FRAME]
        test_failure_items = [e for e in evidence_list if e.type == EvidenceType.TEST_FAILURE]
        resolved_call_items = [
            e for e in evidence_list
            if e.type == EvidenceType.CALL_RELATIONSHIP
            and e.metadata.get("resolution_status") == ResolutionStatus.RESOLVED.value
        ]
        resolved_symbols = [
            e for e in evidence_list
            if e.type == EvidenceType.SYMBOL
            and e.metadata.get("resolution_status") != ResolutionStatus.UNRESOLVED.value
        ]
        recent_commit_items = [e for e in evidence_list if e.type == EvidenceType.COMMIT]

        # Case: completely generic without actionable frames, tests, or symbols
        if not stack_frame_items and not test_failure_items and not resolved_symbols:
            missing_info.append("Missing stack trace or failing test location.")
            missing_info.append("Unable to resolve any repository symbol from error report.")
            return EvidenceSufficiency.INSUFFICIENT, missing_info

        # If only generic message and low-relevance items
        if is_generic_msg and not stack_frame_items and not test_failure_items:
            missing_info.append("Error message is generic; missing reproducible stack trace or failing test.")
            return EvidenceSufficiency.INSUFFICIENT, missing_info

        # Sufficient conditions:
        # 1. Direct stack frame with resolved location and call relationship or recent change
        has_resolved_stack_frame = any(
            sf.metadata.get("resolution_status") == ResolutionStatus.RESOLVED.value
            for sf in stack_frame_items
        )
        if has_resolved_stack_frame and (resolved_call_items or recent_commit_items or test_failure_items):
            return EvidenceSufficiency.SUFFICIENT, missing_info

        # 2. Failing test with resolved tested source relationship
        has_resolved_test = any(
            tf.metadata.get("tested_file") or tf.metadata.get("resolution_status") == ResolutionStatus.RESOLVED.value
            for tf in test_failure_items
        )
        if has_resolved_test and (resolved_symbols or resolved_call_items or recent_commit_items):
            return EvidenceSufficiency.SUFFICIENT, missing_info

        # 3. Direct stack frame present, even if intra-module call
        if stack_frame_items and (resolved_symbols or len(stack_frame_items) >= 2):
            return EvidenceSufficiency.SUFFICIENT, missing_info

        # Partially sufficient conditions:
        if stack_frame_items and not test_failure_items:
            missing_info.append("Stack trace located, but no dedicated regression test exists for verification.")
            return EvidenceSufficiency.PARTIALLY_SUFFICIENT, missing_info

        if test_failure_items and not stack_frame_items:
            missing_info.append("Failing test identified, but direct stack trace into failing module is missing.")
            return EvidenceSufficiency.PARTIALLY_SUFFICIENT, missing_info

        if resolved_symbols:
            missing_info.append("Suspected symbol identified, but exact failure execution path is ambiguous.")
            return EvidenceSufficiency.PARTIALLY_SUFFICIENT, missing_info

        missing_info.append("Insufficient corroborating evidence across call graph and test suite.")
        return EvidenceSufficiency.INSUFFICIENT, missing_info
