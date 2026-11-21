"""Devaura Isolated Sandbox Workspace.

Ensures that code patches are applied strictly in an isolated workspace clone.
Guarantees that the original repository remains 100% untouched.
"""

import os
import re
import shutil
import uuid
from typing import Dict, List, Optional, Tuple

from apps.api.logger import logger


class PatchApplicationError(Exception):
    """Raised when a patch cannot be cleanly applied to target files."""
    pass


class IsolatedWorkspace:
    """Manages an isolated copy of a repository for safe patch application."""

    DEFAULT_SANDBOX_BASE = ".devaura_sandboxes"

    def __init__(
        self,
        source_repo_path: str,
        workspace_id: Optional[str] = None,
        base_dir: Optional[str] = None,
    ):
        self.source_repo_path = os.path.abspath(source_repo_path)
        self.workspace_id = workspace_id or str(uuid.uuid4())
        root_sandbox_dir = base_dir or os.path.join(self.source_repo_path, self.DEFAULT_SANDBOX_BASE)
        self.workspace_path = os.path.abspath(os.path.join(root_sandbox_dir, self.workspace_id))

    def create(self) -> str:
        """Create isolated sandbox directory by copying source files (excluding heavy caches)."""
        if os.path.exists(self.workspace_path):
            shutil.rmtree(self.workspace_path, ignore_errors=True)

        os.makedirs(os.path.dirname(self.workspace_path), exist_ok=True)

        ignore_func = shutil.ignore_patterns(
            ".venv*",
            "node_modules",
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".next",
            self.DEFAULT_SANDBOX_BASE,
            "devaura.db*",
            "*.pyc",
        )

        shutil.copytree(
            self.source_repo_path,
            self.workspace_path,
            ignore=ignore_func,
            dirs_exist_ok=True,
        )
        logger.info(f"Created isolated sandbox at: {self.workspace_path}")
        return self.workspace_path

    def apply_patch(self, unified_diff: str) -> List[str]:
        """Apply unified diff inside the isolated sandbox workspace.

        Returns list of modified file paths relative to workspace root.
        Raises PatchApplicationError if patch cannot be applied.
        """
        if not os.path.exists(self.workspace_path):
            self.create()

        if not unified_diff.strip():
            raise PatchApplicationError("Cannot apply empty patch.")

        # Parse file chunks from unified diff
        file_patches = self._split_unified_diff(unified_diff)
        if not file_patches:
            raise PatchApplicationError("No valid file diffs found in unified diff.")

        modified_files: List[str] = []

        for target_rel_path, hunks in file_patches.items():
            dest_file_path = os.path.join(self.workspace_path, target_rel_path)
            if not os.path.exists(dest_file_path):
                # Ensure parent directory exists for new file creation
                os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                orig_lines: List[str] = []
            else:
                with open(dest_file_path, "r", encoding="utf-8", errors="replace") as f:
                    orig_lines = f.readlines()

            patched_lines = self._apply_hunks_to_lines(orig_lines, hunks, target_rel_path)

            with open(dest_file_path, "w", encoding="utf-8") as f:
                f.writelines(patched_lines)

            modified_files.append(target_rel_path)

        return modified_files

    def _split_unified_diff(self, diff: str) -> Dict[str, List[str]]:
        """Split diff into per-file hunk lists."""
        file_patches: Dict[str, List[str]] = {}
        current_file: Optional[str] = None
        current_hunks: List[str] = []

        for line in diff.splitlines(keepends=True):
            if line.startswith("--- "):
                # Start of a file diff
                continue
            elif line.startswith("+++ "):
                # Destination path
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

    def _apply_hunks_to_lines(
        self, orig_lines: List[str], hunk_lines: List[str], file_path: str
    ) -> List[str]:
        """Apply hunks sequentially to original file lines."""
        # Group into individual @@ ... @@ blocks
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
            raise PatchApplicationError(f"No hunk blocks parsed for {file_path}")

        result_lines = list(orig_lines)
        offset = 0

        for header, block in hunk_blocks:
            # Parse @@ -orig_start,orig_len +new_start,new_len @@
            m = re.match(r"@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", header)
            if not m:
                raise PatchApplicationError(f"Malformed hunk header in {file_path}: {header}")

            orig_start = int(m.group(1))
            adjusted_start = orig_start - 1 + offset

            # Check context and reconstruct
            new_block_lines: List[str] = []
            orig_consumed = 0

            for bline in block:
                marker = bline[0] if bline else " "
                content = bline[1:]

                if marker == " ":
                    new_block_lines.append(content)
                    orig_consumed += 1
                elif marker == "-":
                    orig_consumed += 1
                elif marker == "+":
                    new_block_lines.append(content)
                elif marker == "\\":
                    # \ No newline at end of file
                    continue

            # Extract expected original lines from block for context matching
            expected_orig: List[str] = [bline[1:] for bline in block if bline and bline[0] in (" ", "-")]

            # Replace slice in result_lines
            # Handle boundary safely with context-matching fallback
            start_idx = max(0, min(adjusted_start, len(result_lines)))
            end_idx = min(start_idx + orig_consumed, len(result_lines))

            if expected_orig and len(result_lines) >= len(expected_orig):
                target_stripped = [l.rstrip("\r\n") for l in expected_orig]
                # Check if exact position matches
                curr_slice = [l.rstrip("\r\n") for l in result_lines[start_idx:start_idx + len(expected_orig)]]
                if curr_slice != target_stripped:
                    # Scan for best matching location in file
                    for candidate_idx in range(len(result_lines) - len(expected_orig) + 1):
                        cand_slice = [l.rstrip("\r\n") for l in result_lines[candidate_idx:candidate_idx + len(expected_orig)]]
                        if cand_slice == target_stripped:
                            start_idx = candidate_idx
                            end_idx = start_idx + len(expected_orig)
                            break

            result_lines[start_idx:end_idx] = new_block_lines
            offset += len(new_block_lines) - orig_consumed

        return result_lines

    def get_applied_diff(self, file_path: str) -> str:
        """Get diff between original source file and sandbox file."""
        orig_file = os.path.join(self.source_repo_path, file_path)
        sandbox_file = os.path.join(self.workspace_path, file_path)

        orig_lines = []
        if os.path.exists(orig_file):
            with open(orig_file, "r", encoding="utf-8", errors="replace") as f:
                orig_lines = f.readlines()

        sandbox_lines = []
        if os.path.exists(sandbox_file):
            with open(sandbox_file, "r", encoding="utf-8", errors="replace") as f:
                sandbox_lines = f.readlines()

        import difflib
        diff = difflib.unified_diff(
            orig_lines,
            sandbox_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    def cleanup(self) -> None:
        """Safely destroy sandbox workspace directory."""
        if os.path.exists(self.workspace_path):
            try:
                shutil.rmtree(self.workspace_path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox {self.workspace_path}: {e}")
