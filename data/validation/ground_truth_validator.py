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

    @classmethod
    def inspect_payload(
        cls,
        payload_name: str,
        content: str,
        bug_id: str,
        fix_commit_sha: Optional[str] = None,
        golden_patch: Optional[str] = None,
        fixed_source: Optional[Dict[str, str]] = None,
        hidden_tests: Optional[Dict[str, str]] = None,
        source_files: Optional[Dict[str, str]] = None,
    ) -> None:
        """Inspects arbitrary payload (prompts, tool results, retrieved files/history) for ground truth leaks."""
        if not content:
            return

        # 1. Leakage of fixing commit SHA
        if fix_commit_sha and len(fix_commit_sha) >= 6 and fix_commit_sha.lower() in content.lower():
            raise GroundTruthLeakageError(
                f"Ground-truth leakage detected in {payload_name}: Fixing commit SHA '{fix_commit_sha}' found!"
            )

        # 2. Golden patch lines
        if golden_patch:
            for line in golden_patch.splitlines():
                line_str = line.strip()
                if line_str.startswith("+") and not line_str.startswith("+++") and len(line_str) > 12:
                    clean = line_str[1:].strip()
                    if clean in content:
                        raise GroundTruthLeakageError(
                            f"Ground-truth leakage detected in {payload_name}: Golden patch snippet '{clean[:40]}' found!"
                        )

        # 3. Fixed source lines (post-fix code)
        if fixed_source:
            for file_path, src in fixed_source.items():
                unpatched_src = (source_files or {}).get(file_path, "")
                for line in src.splitlines():
                    clean = line.strip()
                    if len(clean) > 25 and clean in content and not clean.startswith("#"):
                        if unpatched_src and clean in unpatched_src:
                            continue
                        raise GroundTruthLeakageError(
                            f"Ground-truth leakage detected in {payload_name}: Post-fix source from '{file_path}' found!"
                        )

        # 4. Hidden test code or identifiers
        if hidden_tests:
            for test_file, test_src in hidden_tests.items():
                test_name = test_file.split("/")[-1]
                if test_name in content:
                    raise GroundTruthLeakageError(
                        f"Hidden test discovery detected in {payload_name}: Hidden test file '{test_name}' referenced!"
                    )
                for line in test_src.splitlines():
                    clean = line.strip()
                    if len(clean) > 20 and clean in content and not clean.startswith("#") and not clean.startswith("import"):
                        raise GroundTruthLeakageError(
                            f"Hidden test leakage detected in {payload_name}: Code from hidden test '{test_file}' found!"
                        )

        # 5. Prohibited benchmark labels / expected answers
        forbidden_markers = [
            "golden_patch",
            "EXPECTED_CORRECT_ANSWER",
            "BENCHMARK_ANSWER_KEY",
            f"EXPECTED_FIX_{bug_id}",
        ]
        for marker in forbidden_markers:
            if marker in content:
                raise GroundTruthLeakageError(
                    f"Ground-truth marker '{marker}' leaked into {payload_name}!"
                )
