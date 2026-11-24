"""Devaura Patch Structural Validator.

Enforces structural and syntactic integrity on proposed patches before sandbox execution:
1. Hard repository-manifest invariant: All patch targets must exist in indexed repository manifest.
2. Unified diff structural validity: Verifies non-empty diff and valid chunk headers.
3. In-memory patch simulation: Simulates hunk application against original file lines.
4. Python AST parsing: Uses ast.parse() on patched content to reject syntax, indentation, and token errors.
"""

import ast
import os
import re
from typing import Dict, List, Optional, Tuple

from apps.api.logger import logger


class PatchStructuralValidationError(Exception):
    """Raised when a patch fails structural, syntactic, or manifest validation."""

    def __init__(self, message: str, category: str = "PATCH_SYNTAX_FAILURE"):
        super().__init__(message)
        self.message = message
        self.category = category


class PatchStructuralValidator:
    """Validates structural and syntactic integrity of patches before application."""

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def validate(
        self,
        unified_diff: str,
        changed_files: List[str],
    ) -> Tuple[bool, Optional[str], str]:
        """Validate patch structural integrity and Python AST parseability.

        Returns:
            (is_valid, error_message, failure_category)
        """
        if not unified_diff or not unified_diff.strip():
            return False, "Patch diff is empty.", "PATCH_SYNTAX_FAILURE"

        # 1. Manifest Invariant: Target files must exist in repository manifest
        for rel_path in changed_files:
            clean_path = rel_path.replace("\\", "/").strip()
            if not clean_path:
                continue

            # Check traversal or absolute paths
            if ".." in clean_path.split("/") or clean_path.startswith("/") or (len(clean_path) > 1 and clean_path[1] == ":"):
                return (
                    False,
                    f"Security violation: path traversal or absolute path detected in target '{clean_path}'",
                    "PATCH_SCOPE_FAILURE",
                )

            full_path = os.path.join(self.workspace_root, clean_path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                return (
                    False,
                    f"Repository manifest violation: target file '{clean_path}' does not exist in workspace manifest.",
                    "PATCH_SCOPE_FAILURE",
                )

        # 2. Split hunks per file
        try:
            file_patches = self._split_unified_diff(unified_diff)
        except Exception as e:
            return False, f"Malformed unified diff: {e}", "PATCH_SYNTAX_FAILURE"

        if not file_patches:
            return False, "No valid file diffs found in patch.", "PATCH_SYNTAX_FAILURE"

        # 3. Simulate application and parse AST for Python files
        for target_rel_path, hunks in file_patches.items():
            clean_target = target_rel_path.replace("\\", "/").strip()
            full_path = os.path.join(self.workspace_root, clean_target)

            if not os.path.exists(full_path):
                return (
                    False,
                    f"Repository manifest violation: target file '{clean_target}' does not exist in repository manifest.",
                    "PATCH_SCOPE_FAILURE",
                )

            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    orig_lines = f.readlines()
            except Exception as e:
                return False, f"Failed to read source file '{clean_target}': {e}", "PATCH_APPLY_FAILURE"

            try:
                patched_lines = self._simulate_hunks(orig_lines, hunks, clean_target)
            except Exception as e:
                return False, f"Malformed diff hunk application error for '{clean_target}': {e}", "PATCH_APPLY_FAILURE"

            # 4. AST Validation for Python files
            if clean_target.endswith(".py"):
                patched_source = "".join(patched_lines)
                try:
                    ast.parse(patched_source, filename=clean_target)
                except (SyntaxError, IndentationError, TabError) as syn_err:
                    msg = (
                        f"Python structural syntax error in '{clean_target}' at line {syn_err.lineno}: "
                        f"{syn_err.msg} (offset: {syn_err.offset})"
                    )
                    logger.warning(f"PatchStructuralValidator caught syntax error: {msg}")
                    return False, msg, "PATCH_SYNTAX_FAILURE"
                except Exception as ast_err:
                    msg = f"Failed to parse AST for '{clean_target}': {ast_err}"
                    return False, msg, "PATCH_SYNTAX_FAILURE"

        return True, None, "NONE"

    def validate_or_raise(self, unified_diff: str, changed_files: List[str]) -> None:
        """Validate patch or raise PatchStructuralValidationError."""
        is_valid, err_msg, category = self.validate(unified_diff, changed_files)
        if not is_valid:
            raise PatchStructuralValidationError(err_msg or "Patch structural validation failed", category=category)

    def _split_unified_diff(self, diff: str) -> Dict[str, List[str]]:
        """Extract per-file hunk lines from unified diff."""
        file_patches: Dict[str, List[str]] = {}
        current_file: Optional[str] = None
        current_hunks: List[str] = []

        for line in diff.splitlines(keepends=True):
            if line.startswith("--- "):
                continue
            elif line.startswith("+++ "):
                if current_file and current_hunks:
                    file_patches[current_file] = current_hunks
                    current_hunks = []
                raw_path = line[4:].strip()
                if raw_path.startswith("b/"):
                    raw_path = raw_path[2:]
                current_file = os.path.normpath(raw_path).replace("\\", "/")
            elif current_file is not None:
                current_hunks.append(line)

        if current_file and current_hunks:
            file_patches[current_file] = current_hunks

        return file_patches

    def _simulate_hunks(
        self, orig_lines: List[str], hunk_lines: List[str], file_path: str
    ) -> List[str]:
        """Simulate applying hunks sequentially to lines in memory."""
        hunk_blocks: List[Tuple[str, List[str]]] = []
        current_header: Optional[str] = None
        current_block: List[str] = []

        for hline in hunk_lines:
            if hline.startswith("@@"):
                if current_header:
                    hunk_blocks.append((current_header, current_block))
                    current_block = []
                current_header = hline
            elif current_header:
                current_block.append(hline)

        if current_header:
            hunk_blocks.append((current_header, current_block))

        if not hunk_blocks:
            raise ValueError(f"No hunk blocks parsed for {file_path}")

        result_lines = list(orig_lines)
        offset = 0

        for header, block in hunk_blocks:
            m = re.match(r"@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", header)
            if not m:
                raise ValueError(f"Malformed hunk header in {file_path}: {header}")

            orig_start = int(m.group(1))
            adjusted_start = orig_start - 1 + offset

            new_block_lines: List[str] = []
            orig_consumed = 0

            for bline in block:
                marker = bline[0] if bline else " "
                content = bline[1:]
                if not content.endswith("\n"):
                    content += "\n"

                if marker == " ":
                    new_block_lines.append(content)
                    orig_consumed += 1
                elif marker == "-":
                    orig_consumed += 1
                elif marker == "+":
                    new_block_lines.append(content)
                elif marker == "\\":
                    continue

            expected_orig: List[str] = [bline[1:] for bline in block if bline and bline[0] in (" ", "-")]

            start_idx = max(0, min(adjusted_start, len(result_lines)))
            end_idx = min(start_idx + orig_consumed, len(result_lines))

            if expected_orig and len(result_lines) >= len(expected_orig):
                target_stripped = [l.rstrip("\r\n") for l in expected_orig]
                curr_slice = [l.rstrip("\r\n") for l in result_lines[start_idx:start_idx + len(expected_orig)]]
                if curr_slice != target_stripped:
                    for candidate_idx in range(len(result_lines) - len(expected_orig) + 1):
                        cand_slice = [l.rstrip("\r\n") for l in result_lines[candidate_idx:candidate_idx + len(expected_orig)]]
                        if cand_slice == target_stripped:
                            start_idx = candidate_idx
                            end_idx = start_idx + len(expected_orig)
                            break

            result_lines[start_idx:end_idx] = new_block_lines
            offset += len(new_block_lines) - orig_consumed

        return result_lines
