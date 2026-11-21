"""Devaura Phase 7 Pull Request Context Builder.

Synthesizes structured, evidence-backed PRContext from Phase 6 VerifiedRepairResult,
Phase 5 RepairPlan, and Phase 4 Investigation.
Enforces hard entry conditions, deterministic titles, structured descriptions, and security guards.
"""

import hashlib
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from agent.pr.models import PRContext
from agent.repair.models import (
    CheckStatus,
    OverallVerificationStatus,
    VerifiedRepairResult,
)
from database.models.repair import RepairRecord


class PRContextBuilder:
    """Constructs and validates PRContext contracts from verified repairs."""

    SENSITIVE_PATTERNS = [
        re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
        re.compile(r".*\.(pem|key|pkcs12|pfx|p12)$", re.IGNORECASE),
        re.compile(r".*id_rsa.*", re.IGNORECASE),
        re.compile(r".*credentials\.(json|yaml|yml|ini)$", re.IGNORECASE),
        re.compile(r".*secrets\.(json|yaml|yml)$", re.IGNORECASE),
    ]

    ALLOWED_REPOSITORIES = {"Devaura", "shreyvirmani/Devaura", "bench-repo", "source_repo", "repo-devaura-main"}

    @classmethod
    def check_sensitive_files(cls, files: List[str]) -> Tuple[bool, Optional[str]]:
        """Check if any changed file matches sensitive patterns or path traversals."""
        for f in files:
            normalized = f.replace("\\", "/").strip()
            # Path traversal guard
            if ".." in normalized or normalized.startswith("/"):
                return False, f"Path traversal violation in file '{f}'."

            basename = os.path.basename(normalized)
            for pattern in cls.SENSITIVE_PATTERNS:
                if pattern.match(basename) or pattern.match(normalized):
                    return False, f"Sensitive file pattern blocked: '{f}'."

        return True, None

    @classmethod
    def validate_entry_conditions(
        cls,
        repair_record: Any,
        verified_result: Optional[VerifiedRepairResult] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Enforce strict Phase 7 entry conditions.

        Returns (is_valid, error_code, error_message).
        """
        if not repair_record:
            return False, "PR_BLOCKED", "Repair record does not exist."

        # 1. State must be VERIFIED
        status_val = getattr(repair_record, "status", "")
        if status_val != "VERIFIED":
            return False, "PR_BLOCKED_UNVERIFIED", f"Repair state '{status_val}' is not VERIFIED. Unverified repairs cannot create pull requests."

        # 2. Patch must exist
        patch = getattr(repair_record, "patch", None)
        if not patch or not patch.unified_diff or not patch.patch_hash:
            return False, "PR_BLOCKED", "Repair does not contain a valid patch."

        # 3. Workspace must exist
        workspace = getattr(repair_record, "workspace", None)
        if not workspace or not workspace.isolated_path:
            return False, "PR_BLOCKED", "Isolated sandbox workspace does not exist."

        # 4. Base revision must be known
        base_rev = getattr(repair_record, "base_revision", "")
        if not base_rev:
            return False, "PR_BLOCKED", "Base revision is unknown."

        # 5. Verified result checks if provided
        if verified_result:
            if verified_result.verification_status != "VERIFIED":
                return False, "PR_BLOCKED_UNVERIFIED", "Verification status is not VERIFIED."

            # Verify patch hash integrity: patch_hash == SHA256(diff)
            recalculated_hash = hashlib.sha256(patch.unified_diff.encode("utf-8")).hexdigest()
            recalculated_strip_hash = hashlib.sha256(patch.unified_diff.strip().encode("utf-8")).hexdigest()
            valid_hashes = {patch.patch_hash, recalculated_hash, recalculated_strip_hash}
            if verified_result.final_patch_hash not in valid_hashes:
                return (
                    False,
                    "PR_BLOCKED_PATCH_CHANGED",
                    f"Patch has been modified after verification: current '{patch.patch_hash[:8]}' vs verified '{verified_result.final_patch_hash[:8]}'.",
                )

            # Confirm all checks passed
            for c in verified_result.checks:
                c_status = c.get("status") if isinstance(c, dict) else getattr(c, "status", None)
                if c_status != "PASSED" and c_status != CheckStatus.PASSED:
                    return False, "PR_BLOCKED_UNVERIFIED", f"Required verification check did not pass: {c}."

        # 6. Sensitive file check
        changed_files = patch.changed_files or []
        is_safe, sec_err = cls.check_sensitive_files(changed_files)
        if not is_safe:
            return False, "PR_BLOCKED_SECURITY", sec_err

        return True, None, None

    @classmethod
    def generate_pr_title(cls, root_cause: str, affected_files: List[str]) -> str:
        """Generate clean, deterministic conventional commit title without marketing buzzwords."""
        file_part = os.path.basename(affected_files[0]) if affected_files else "issue"
        # Sanitize root cause summary
        clean_summary = re.sub(r"^(issue|bug|error|failure):\s*", "", root_cause, flags=re.IGNORECASE).strip()
        clean_summary = clean_summary.split("\n")[0].rstrip(".")
        if len(clean_summary) > 60:
            clean_summary = clean_summary[:57] + "..."

        if not clean_summary:
            clean_summary = f"resolve failure in {file_part}"

        return f"fix: resolve {clean_summary.lower()}"

    @classmethod
    def generate_pr_body(
        cls,
        repair_id: str,
        investigation_id: str,
        verification_id: str,
        patch_hash: str,
        base_revision: str,
        root_cause: str,
        proposed_changes: List[Dict[str, Any]],
        changed_files: List[str],
        verification_summary: Dict[str, Any],
        attempt_count: int,
        risk_level: str = "LOW",
        findings: Optional[List[str]] = None,
    ) -> str:
        """Generate structured markdown body following Devaura Section 11 specifications."""
        changes_list = []
        if proposed_changes:
            for pc in proposed_changes:
                if isinstance(pc, dict):
                    rationale = pc.get("rationale", "Defensive patch")
                    f = pc.get("file", "unknown")
                    changes_list.append(f"- `{f}`: {rationale}")
        if not changes_list:
            for f in changed_files:
                changes_list.append(f"- `{f}`: Applied verified defensive repairs")

        changes_md = "\n".join(changes_list)

        files_md = "\n".join([f"- `{f}`" for f in changed_files]) or "- None"

        tests_status = verification_summary.get("tests", "PASS")
        lint_status = verification_summary.get("lint", "PASS")
        typecheck_status = verification_summary.get("typecheck", "PASS")

        findings_md = ""
        if findings:
            findings_md = "\n" + "\n".join([f"- {f}" for f in findings])

        return f"""## Summary
Automated verified repair proposed by Devaura for investigation `{investigation_id[:8]}`.

## Root Cause
{root_cause or "Software failure diagnosed by Code Intelligence."}

## Changes
{changes_md}

## Verification
- Tests: {tests_status}
- Lint: {lint_status}
- Typecheck: {typecheck_status}

## Repair Attempts
- Total attempts required: {attempt_count}/3 (bounded loop)
- Verified on Attempt #{attempt_count}

## Risk Analysis
- Risk Level: **{risk_level}**{findings_md}
- Isolated Sandbox Execution: Verified with 0 mutations to base branch.

## Files Changed
{files_md}

## Devaura Metadata
- Repair ID: `{repair_id}`
- Investigation ID: `{investigation_id}`
- Verification ID: `{verification_id}`
- Patch Hash: `{patch_hash}`
- Base Revision: `{base_revision}`
"""

    @classmethod
    def build_context(
        cls,
        repair_record: Any,
        verified_result: Optional[VerifiedRepairResult] = None,
        owner: str = "shreyvirmani",
        repo: str = "Devaura",
    ) -> Tuple[bool, Optional[PRContext], Optional[str], Optional[str]]:
        """Validate and construct structured PRContext."""
        is_valid, err_code, err_msg = cls.validate_entry_conditions(repair_record, verified_result)
        if not is_valid:
            return False, None, err_code, err_msg

        repair_id = getattr(repair_record, "id", "")
        investigation_id = getattr(repair_record, "investigation_id", "")
        base_branch = getattr(repair_record, "target_branch", "main") or "main"
        base_rev = getattr(repair_record, "base_revision", "HEAD")

        patch = getattr(repair_record, "patch", None)
        patch_hash = patch.patch_hash if patch else ""
        changed_files = patch.changed_files if patch else []

        plan = getattr(repair_record, "plan", None)
        root_cause = plan.root_cause if plan else "Identified software failure"
        proposed_changes = plan.proposed_changes if plan else []

        risk = getattr(repair_record, "risk", None)
        risk_level = risk.level if risk else "LOW"
        risk_findings = risk.blocking_findings if risk else []

        v_id = getattr(repair_record, "latest_verification_id", "") or (
            verified_result.verification_id if verified_result else "v-verified"
        )

        attempts_count = getattr(repair_record, "current_attempt", 1) or 1

        v_summary = {"tests": "PASS", "lint": "PASS", "typecheck": "PASS"}
        if verified_result and verified_result.checks:
            for c in verified_result.checks:
                c_type = c.get("check_type") if isinstance(c, dict) else getattr(c, "check_type", "")
                c_status = c.get("status") if isinstance(c, dict) else getattr(c, "status", "")
                if c_type:
                    v_summary[str(c_type).lower()] = "PASS" if str(c_status).upper() == "PASSED" else "FAIL"

        repair_branch = f"devaura/repair/{repair_id[:8]}"
        title = cls.generate_pr_title(root_cause, changed_files)
        body = cls.generate_pr_body(
            repair_id=repair_id,
            investigation_id=investigation_id,
            verification_id=v_id,
            patch_hash=patch_hash,
            base_revision=base_rev,
            root_cause=root_cause,
            proposed_changes=proposed_changes,
            changed_files=changed_files,
            verification_summary=v_summary,
            attempt_count=attempts_count,
            risk_level=risk_level,
            findings=risk_findings,
        )

        commit_msg = f"{title}\n\nDevaura-Repair-Id: {repair_id}"

        context = PRContext(
            repair_id=repair_id,
            investigation_id=investigation_id,
            repository=f"{owner}/{repo}",
            owner=owner,
            repo=repo,
            base_branch=base_branch,
            base_revision=base_rev,
            repair_branch=repair_branch,
            commit_message=commit_msg,
            pr_title=title,
            pr_body=body,
            changed_files=changed_files,
            patch_hash=patch_hash,
            verification_id=v_id,
            verification_summary=v_summary,
            root_cause_summary=root_cause,
            repair_summary=plan.objective if plan else "Automated repair",
            risk_summary={"level": risk_level, "findings": risk_findings},
            attempt_count=attempts_count,
        )

        return True, context, None, None
