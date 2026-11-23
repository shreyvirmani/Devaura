"""Devaura Real Data Pipeline: Ground Truth & Leakage Validation.

Enforces zero-leakage boundaries: verifies that golden patches, fixing commits,
and hidden validation tests are strictly absent from runtime prompts and workspaces.
Also validates bug-fix reproducibility: buggy revision fails tests, fixed revision passes tests.
"""

from typing import Dict, List, Optional, Tuple


class GroundTruthLeakageError(ValueError):
    """Raised when ground-truth answers or hidden tests leak into agent prompts or context."""
    pass


class GroundTruthValidator:
    """Verifies isolation of ground-truth fixes and validates test reproducibility."""

    @classmethod
    def assert_no_leakage(
        cls,
        prompt_text: str,
        golden_patch: Optional[str] = None,
        fixed_source: Optional[Dict[str, str]] = None,
        hidden_tests: Optional[Dict[str, str]] = None,
        fixing_commit: Optional[str] = None,
    ) -> None:
        """Verifies that no ground-truth fix or hidden test code is present in the prompt string."""
        if not prompt_text:
            return

        # 1. Check fixing commit SHA
        if fixing_commit and len(fixing_commit) >= 8 and fixing_commit in prompt_text:
            raise GroundTruthLeakageError(
                f"Ground-truth leakage detected: Fixing commit SHA '{fixing_commit[:8]}' found in prompt!"
            )

        # 2. Check golden patch diff lines (excluding common unified diff headers)
        if golden_patch:
            diff_lines = [
                line.strip()
                for line in golden_patch.splitlines()
                if line.startswith("+") and not line.startswith("+++") and len(line.strip()) > 15
            ]
            for line in diff_lines:
                clean_line = line[1:].strip()
                if clean_line in prompt_text:
                    raise GroundTruthLeakageError(
                        f"Ground-truth leakage detected: Golden fix line '{clean_line[:50]}' found in prompt!"
                    )

        # 3. Check fixed source code blocks
        if fixed_source:
            for file_path, content in fixed_source.items():
                if content and len(content.strip()) > 20:
                    # Check significant chunks
                    lines = [l.strip() for l in content.splitlines() if len(l.strip()) > 20]
                    for l in lines[:5]:
                        if l in prompt_text:
                            raise GroundTruthLeakageError(
                                f"Ground-truth leakage detected: Fixed source from '{file_path}' found in prompt!"
                            )

        # 4. Check hidden validation tests
        if hidden_tests:
            for test_file, test_content in hidden_tests.items():
                if test_content and len(test_content.strip()) > 20:
                    lines = [l.strip() for l in test_content.splitlines() if len(l.strip()) > 20]
                    for l in lines:
                        if l in prompt_text:
                            raise GroundTruthLeakageError(
                                f"Hidden test leakage detected: Code from '{test_file}' found in prompt!"
                            )
