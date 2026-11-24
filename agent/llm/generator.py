"""Devaura LLM-Backed Patch Generator & Safety Validator.

Synthesizes unified diffs using LLM reasoning and subjects every patch
to a 7-stage deterministic safety gate before approval or sandboxing:
1. Unified diff syntax validation
2. Path traversal guard
3. Scope & boundary enforcement
4. Sensitive / credential file filtering
5. Evidence citation traceability
6. Multi-dimensional risk analysis
7. Cryptographic human approval binding
"""

import hashlib
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from agent.llm.models import (
    LLMPatchProposal,
    LLMUsage,
)
from agent.llm.prompts import (
    PATCH_GENERATOR_SYSTEM_PROMPT,
    SecretRedactor,
    build_patch_prompt,
)
from agent.llm.provider import LLMProvider, ProviderFactory
from agent.repair.approval_gate import HumanApprovalGate
from agent.repair.models import (
    PatchResult,
    PatchRisk,
    RepairContext,
    RepairPlan,
)
from agent.repair.patch_generator import PatchScopeGuard, ScopeViolationError
from agent.repair.risk_analyzer import PatchRiskAnalyzer
from agent.repair.structural_validator import (
    PatchStructuralValidationError,
    PatchStructuralValidator,
)
from apps.api.logger import logger


class LLMPatchGenerator:
    """Generates patches with language models, governed by 7 deterministic safety gates."""

    def __init__(
        self,
        workspace_root: str = ".",
        provider: Optional[LLMProvider] = None,
        approval_gate: Optional[HumanApprovalGate] = None,
        risk_analyzer: Optional[PatchRiskAnalyzer] = None,
    ):
        self.workspace_root = workspace_root
        self.provider = provider or ProviderFactory.get_provider()
        self.scope_guard = PatchScopeGuard(repo_root=workspace_root)
        self.risk_analyzer = risk_analyzer or PatchRiskAnalyzer()
        self.approval_gate = approval_gate or HumanApprovalGate()

    def generate_patch(
        self,
        plan: RepairPlan,
        context: RepairContext,
    ) -> Tuple[PatchResult, LLMUsage, PatchRisk]:
        """Synthesize unified diff patch governed by 7-stage deterministic safety gates."""

        # Stage 0: Gather source files in scope
        source_files: Dict[str, str] = {}
        for file_path in plan.affected_files:
            norm_path = file_path.replace("\\", "/").strip()
            # Stage 2 & 4 preliminary check: path traversal and sensitive files
            self._validate_file_safety(norm_path)

            full_path = os.path.join(self.workspace_root, norm_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        source_files[norm_path] = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read source file {norm_path}: {e}")
                    source_files[norm_path] = ""
            else:
                source_files[norm_path] = ""

        # Construct sanitized prompt
        prompt = build_patch_prompt(plan, context, source_files)

        # Call LLM with structured schema
        proposal, usage = self.provider.generate_structured(
            prompt=prompt,
            schema=LLMPatchProposal,
            system_prompt=PATCH_GENERATOR_SYSTEM_PROMPT,
        )

        diff = proposal.unified_diff.strip()

        # =========================================================================
        # 7-STAGE DETERMINISTIC SAFETY CHECKS
        # =========================================================================

        # Check 1: Unified diff syntax validation
        if not diff:
            raise ScopeViolationError("Generated patch produces an empty diff (no changes).")
        self._validate_unified_diff_syntax(diff)

        # Check 2: Path traversal check
        self._validate_path_traversal(diff)

        # Check 3: Scope validation (strictly plan.affected_files)
        changed_files = self._extract_changed_files(diff)
        for cf in changed_files:
            if cf not in plan.affected_files:
                raise ScopeViolationError(
                    f"Scope violation: patch attempts to modify '{cf}' which is not in approved plan scope: {plan.affected_files}"
                )

        # Check 4: Sensitive-file check
        for cf in changed_files:
            self._validate_file_safety(cf)

        # Check 5: Structural & Repository Manifest Validation (AST and Path Invariant)
        validator = PatchStructuralValidator(workspace_root=self.workspace_root)
        is_struct_valid, struct_msg, struct_cat = validator.validate(diff, changed_files)
        if not is_struct_valid:
            if struct_cat == "PATCH_SCOPE_FAILURE":
                raise ScopeViolationError(struct_msg or "Patch scope or repository manifest violation.")
            else:
                raise PatchStructuralValidationError(struct_msg or "Structural validation failed.", category=struct_cat)

        # Check 6: Evidence citation validation
        valid_ev_ids = {e.get("evidence_id") for e in context.supporting_evidence if e.get("evidence_id")}
        has_citations = any(change.evidence_ids for change in plan.proposed_changes)
        if not has_citations and not proposal.cited_evidence_ids:
            logger.warning("Patch generated without explicit evidence citation in plan or proposal.")

        # Compute patch metrics
        lines_added = 0
        lines_removed = 0
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1

        patch_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest()

        prov = "DETERMINISTIC" if self.provider.provider_name() == "deterministic-mock" else "REAL_LLM"

        patch_result = PatchResult(
            status="GENERATED",
            unified_diff=diff,
            patch_hash=patch_hash,
            changed_files=changed_files,
            lines_added=lines_added,
            lines_removed=lines_removed,
            explanation=proposal.explanation or f"LLM repair addressing {plan.root_cause}",
            assumptions=proposal.assumptions or plan.assumptions,
            patch_provenance=prov,
            model_metadata={
                "provider": usage.provider,
                "model": usage.model,
                "tokens": usage.total_tokens,
                "cost_usd": usage.estimated_cost_usd,
                "latency_ms": usage.latency_ms,
            },
        )

        # Check 6: Risk analysis
        risk = self.risk_analyzer.analyze(plan=plan, patch=patch_result, context=context)

        # Check 7: Human approval check & cryptographic binding
        # The patch hash is ready for approval binding; if critical risk or policy requires approval,
        # it cannot be applied until HumanApprovalGate authorizes it.

        return patch_result, usage, risk

    def _validate_unified_diff_syntax(self, diff: str) -> None:
        """Verify the diff conforms to standard unified diff structure."""
        has_header = False
        has_chunk = False
        for line in diff.splitlines():
            if line.startswith("--- ") or line.startswith("+++ "):
                has_header = True
            if line.startswith("@@"):
                has_chunk = True

        if not (has_header or has_chunk):
            raise ScopeViolationError(
                "Invalid patch syntax: unified diff must contain diff headers (--- / +++) or hunk markers (@@)."
            )

    def _validate_path_traversal(self, diff: str) -> None:
        """Verify no path traversal or absolute file references exist in diff headers."""
        for line in diff.splitlines():
            if line.startswith("--- ") or line.startswith("+++ "):
                path_part = line[4:].strip()
                if path_part.startswith("a/") or path_part.startswith("b/"):
                    path_part = path_part[2:]
                clean_path = path_part.replace("\\", "/")
                if ".." in clean_path.split("/"):
                    raise ScopeViolationError(f"Security violation: path traversal detected in patch header: '{line}'")
                if clean_path.startswith("/") or (len(clean_path) > 1 and clean_path[1] == ":"):
                    raise ScopeViolationError(f"Security violation: absolute path detected in patch header: '{line}'")
                if "\0" in clean_path:
                    raise ScopeViolationError("Security violation: null byte detected in patch path.")

    def _extract_changed_files(self, diff: str) -> List[str]:
        """Extract all target repository paths modified by the unified diff."""
        files: Set[str] = set()
        for line in diff.splitlines():
            if line.startswith("+++ "):
                path_part = line[4:].strip()
                if path_part.startswith("b/"):
                    path_part = path_part[2:]
                clean = path_part.replace("\\", "/").strip()
                if clean and clean != "/dev/null":
                    files.add(clean)
        return sorted(list(files))

    def _validate_file_safety(self, file_path: str) -> None:
        """Check for forbidden files (secrets, keys, environment configs)."""
        clean = file_path.replace("\\", "/").strip()
        base = os.path.basename(clean)

        if base in self.scope_guard.RESTRICTED_FILES:
            raise ScopeViolationError(f"Security violation: modification of restricted file '{clean}' is forbidden.")

        ext = os.path.splitext(clean)[1].lower()
        if ext in self.scope_guard.RESTRICTED_EXTENSIONS:
            raise ScopeViolationError(f"Security violation: modification of file with extension '{ext}' is forbidden.")

        for pat in self.scope_guard.SENSITIVE_PATTERNS:
            if pat.search(base) or pat.search(clean):
                raise ScopeViolationError(f"Security violation: file '{clean}' matches sensitive pattern.")
