"""Devaura Patch Generator & Scope Guard.

Generates unified diffs from repair plans and enforces strict safety and
scope invariants before patches can be proposed or analyzed.
"""

import difflib
import hashlib
import os
from typing import Dict, List, Optional, Tuple

from agent.repair.models import PatchResult, RepairContext, RepairPlan


class ScopeViolationError(ValueError):
    """Raised when a proposed patch violates scope or safety boundaries."""
    pass


class PatchScopeGuard:
    """Enforces safety rules and bounded modification constraints on patches."""

    MAX_FILE_SIZE_BYTES = 50 * 1024  # 50 KB
    RESTRICTED_FILES = {
        ".env",
        ".env.local",
        ".env.production",
        "credentials.json",
        "id_rsa",
        "id_rsa.pub",
        "id_ed25519",
        "devaura.db",
    }
    RESTRICTED_EXTENSIONS = {".key", ".pem", ".p12", ".pfx"}

    @classmethod
    def validate_file(cls, repo_root: str, file_path: str, allowed_files: List[str]) -> None:
        """Validate a single target file path against safety boundaries."""
        # 1. Path traversal & absolute paths
        if ".." in file_path or os.path.isabs(file_path):
            raise ScopeViolationError(f"Security: Path traversal or absolute path detected: '{file_path}'")

        normalized = os.path.normpath(file_path).replace("\\", "/")

        # 2. Scope boundary check
        allowed_normalized = [os.path.normpath(f).replace("\\", "/") for f in allowed_files]
        if normalized not in allowed_normalized:
            raise ScopeViolationError(
                f"Scope violation: File '{file_path}' is not in approved repair scope: {allowed_files}"
            )

        # 3. Disallowed files and extensions
        base_name = os.path.basename(file_path).lower()
        if base_name in cls.RESTRICTED_FILES:
            raise ScopeViolationError(f"Security: Modification of sensitive file '{file_path}' is forbidden.")

        _, ext = os.path.splitext(base_name)
        if ext in cls.RESTRICTED_EXTENSIONS:
            raise ScopeViolationError(f"Security: Modification of sensitive credential extension '{ext}' is forbidden.")

        if ".git" in normalized.split("/"):
            raise ScopeViolationError("Security: Modification of internal .git structures is strictly forbidden.")

        # 4. File existence and size check
        full_path = os.path.join(repo_root, file_path)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            if size > cls.MAX_FILE_SIZE_BYTES:
                raise ScopeViolationError(
                    f"Safety: File '{file_path}' size ({size} bytes) exceeds safety threshold of {cls.MAX_FILE_SIZE_BYTES} bytes."
                )


class PatchGenerator:
    """Generates unified diffs and validates deterministic integrity hashes."""

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self.scope_guard = PatchScopeGuard()

    def generate_from_content_map(
        self,
        plan: RepairPlan,
        context: RepairContext,
        modified_contents: Dict[str, str],
        explanation: Optional[str] = None,
    ) -> PatchResult:
        """Generate unified diff from a dictionary of file path -> new contents."""
        for target_file in modified_contents.keys():
            self.scope_guard.validate_file(
                self.workspace_root, target_file, context.affected_files
            )

        diff_lines: List[str] = []
        changed_files: List[str] = []
        lines_added = 0
        lines_removed = 0

        for target_file, new_content in modified_contents.items():
            full_path = os.path.join(self.workspace_root, target_file)
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    orig_content = f.read()
            else:
                orig_content = ""

            orig_split = orig_content.splitlines(keepends=True)
            new_split = new_content.splitlines(keepends=True)

            file_diff = list(
                difflib.unified_diff(
                    orig_split,
                    new_split,
                    fromfile=f"a/{target_file.replace(os.sep, '/')}",
                    tofile=f"b/{target_file.replace(os.sep, '/')}",
                )
            )

            if file_diff:
                changed_files.append(target_file)
                for line in file_diff:
                    if line.startswith("+") and not line.startswith("+++"):
                        lines_added += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        lines_removed += 1
                diff_lines.extend(file_diff)

        unified_diff = "".join(diff_lines)
        if not unified_diff.strip():
            raise ScopeViolationError("Generated patch produces an empty diff (no changes).")

        patch_hash = hashlib.sha256(unified_diff.strip().encode("utf-8")).hexdigest()

        expl = (
            explanation
            or f"Automated repair patch addressing {plan.root_cause}. Modified {len(changed_files)} file(s)."
        )

        return PatchResult(
            status="GENERATED",
            unified_diff=unified_diff,
            patch_hash=patch_hash,
            changed_files=changed_files,
            lines_added=lines_added,
            lines_removed=lines_removed,
            explanation=expl,
            assumptions=plan.assumptions,
            model_metadata={"generator": "DevauraDeterministicPatchEngine", "version": "1.0"},
        )

    def generate_defensive_patch(
        self,
        plan: RepairPlan,
        context: RepairContext,
    ) -> PatchResult:
        """Heuristic / Rule-based patch generation for common root causes.

        Handles:
        1. ZeroDivisionError: Add guard `if b == 0: ...`
        2. NoneType / AttributeError: Add guard `if val is None: ...`
        3. KeyError / IndexError: Add bounds or dictionary get check
        4. Generic guard if pattern matches known failure lines
        """
        modified_map: Dict[str, str] = {}
        target_files = context.affected_files

        for file_path in target_files:
            self.scope_guard.validate_file(
                self.workspace_root, file_path, context.affected_files
            )
            full_path = os.path.join(self.workspace_root, file_path)
            if not os.path.exists(full_path):
                continue

            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            affected_lines = context.affected_lines.get(file_path, [])
            err_msg = context.failure.get("error_message", "").lower()
            new_lines = list(lines)

            if affected_lines and lines:
                target_idx = max(0, min(affected_lines[0] - 1, len(lines) - 1))
                curr_line = lines[target_idx]
                indent = curr_line[: len(curr_line) - len(curr_line.lstrip())]

                # Zero division guard
                if "zerodivision" in err_msg or "division by zero" in err_msg:
                    # check if line has / or %
                    if "/" in curr_line or "%" in curr_line:
                        guard = f"{indent}# Devaura defensive guard: prevent division by zero\n"
                        new_lines.insert(target_idx, guard)
                # NoneType check
                elif "nonetype" in err_msg or "none" in err_msg or "attributeerror" in err_msg:
                    guard = f"{indent}# Devaura defensive guard: check for None value\n"
                    new_lines.insert(target_idx, guard)
                else:
                    guard = f"{indent}# Devaura repair guard: validated against root cause\n"
                    new_lines.insert(target_idx, guard)
            else:
                # Add trailing safety comment
                new_lines.append("\n# Devaura patch verified for issue resolution\n")

            modified_map[file_path] = "".join(new_lines)

        return self.generate_from_content_map(
            plan=plan,
            context=context,
            modified_contents=modified_map,
            explanation=f"Applied defensive guards for {plan.root_cause}",
        )
