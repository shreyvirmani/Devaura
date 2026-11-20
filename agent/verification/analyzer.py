"""Devaura Verification Failure Analyzer.

Analyzes verification test/lint/typecheck failures, computes deterministic
failure signatures, classifies code vs infrastructure errors, and determines
bounded retry eligibility (max 3 attempts).
"""

from typing import List, Optional

from agent.repair.models import (
    CheckStatus,
    CheckType,
    FailureAnalysisReport,
    FailureClassification,
    FailureSignature,
    VerificationRun,
)
from agent.verification.normalizer import OutputNormalizer


class VerificationAnalyzer:
    """Diagnoses verification failures and decides whether a repair retry is permissible."""

    MAX_REPAIR_ATTEMPTS = 3

    def __init__(self):
        pass

    def analyze(
        self,
        verification_run: VerificationRun,
        previous_signatures: Optional[List[str]] = None,
        previous_patch_hashes: Optional[List[str]] = None,
        current_patch_hash: Optional[str] = None,
    ) -> FailureAnalysisReport:
        """Perform comprehensive diagnosis on a failed verification run."""
        prev_sigs = set(previous_signatures or [])
        prev_hashes = set(previous_patch_hashes or [])

        # 1. Check for Infrastructure or Timeout Failures
        infra_checks = [c for c in verification_run.checks if c.status == CheckStatus.INFRASTRUCTURE_ERROR]
        if infra_checks:
            first_infra = infra_checks[0]
            return FailureAnalysisReport(
                failure_type=FailureClassification.INFRASTRUCTURE_FAILURE,
                failure_signature="infra_error:" + first_infra.check_type.value,
                root_cause_summary=f"Infrastructure failure during {first_infra.check_type.value}: {first_infra.stderr[:200]}",
                affected_files=[],
                affected_symbols=[],
                can_retry=False,
                retry_block_reason="Infrastructure failures (missing executables or environment errors) cannot be resolved by code repair.",
            )

        timeout_checks = [c for c in verification_run.checks if c.status == CheckStatus.TIMEOUT]
        if timeout_checks:
            first_timeout = timeout_checks[0]
            return FailureAnalysisReport(
                failure_type=FailureClassification.TIMEOUT_ERROR,
                failure_signature="timeout:" + first_timeout.check_type.value,
                root_cause_summary=f"Execution timed out during {first_timeout.check_type.value}.",
                affected_files=[],
                affected_symbols=[],
                can_retry=False,
                retry_block_reason="Execution timeout exceeds resource limits. Automatic retry disabled to prevent runaway processes.",
            )

        blocked_checks = [c for c in verification_run.checks if c.status == CheckStatus.BLOCKED]
        if blocked_checks:
            first_blocked = blocked_checks[0]
            return FailureAnalysisReport(
                failure_type=FailureClassification.SECURITY_BLOCK,
                failure_signature="security_block:" + first_blocked.check_type.value,
                root_cause_summary=f"Security violation blocked check {first_blocked.check_type.value}: {first_blocked.stderr[:200]}",
                affected_files=[],
                affected_symbols=[],
                can_retry=False,
                retry_block_reason="Security policy violation blocked execution.",
            )

        # 2. Extract Code Failures
        failed_checks = [c for c in verification_run.checks if c.status == CheckStatus.FAILED]
        if not failed_checks:
            return FailureAnalysisReport(
                failure_type=FailureClassification.UNKNOWN,
                failure_signature="no_failures_detected",
                root_cause_summary="All checks passed or no errors detected.",
                can_retry=False,
                retry_block_reason="No failures detected.",
            )

        primary_check = failed_checks[0]
        parsed_errors = primary_check.parsed_errors

        affected_files: List[str] = []
        affected_symbols: List[str] = []
        primary_failure = parsed_errors[0] if parsed_errors else None

        if primary_failure:
            sig = OutputNormalizer.compute_failure_signature(primary_check.check_type, primary_failure)
            current_signature = sig.signature_hash
            root_summary = f"{primary_check.check_type.value} failed in {primary_failure.file}: {primary_failure.message}"
            for pe in parsed_errors:
                if pe.file and pe.file != "unknown" and pe.file not in affected_files:
                    affected_files.append(pe.file)
                if pe.test_name and pe.test_name != "unnamed_block" and pe.test_name not in affected_symbols:
                    affected_symbols.append(pe.test_name)
        else:
            current_signature = "unparsed:" + primary_check.check_type.value
            root_summary = f"{primary_check.check_type.value} command failed with exit code {primary_check.exit_code}."

        # 3. Check Attempt Limit (Max 3 total attempts)
        if verification_run.attempt_number >= self.MAX_REPAIR_ATTEMPTS:
            return FailureAnalysisReport(
                failure_type=FailureClassification.CODE_FAILURE,
                failure_signature=current_signature,
                root_cause_summary=root_summary,
                affected_files=affected_files,
                affected_symbols=affected_symbols,
                can_retry=False,
                retry_block_reason=f"Maximum allowed repair attempts ({self.MAX_REPAIR_ATTEMPTS}) exhausted. Stopping repair loop.",
            )

        # 4. Check for Identical Retries / No Progress
        if current_signature in prev_sigs:
            # If current patch is also identical to previous, abort for NO_PROGRESS
            if current_patch_hash and current_patch_hash in prev_hashes:
                return FailureAnalysisReport(
                    failure_type=FailureClassification.CODE_FAILURE,
                    failure_signature=current_signature,
                    root_cause_summary=root_summary,
                    affected_files=affected_files,
                    affected_symbols=affected_symbols,
                    can_retry=False,
                    retry_block_reason="Identical failure signature and identical patch detected with no progress.",
                )

        # 5. Formulate suggestions
        suggestions = []
        if primary_check.check_type == CheckType.TESTS:
            suggestions.append("Refine defensive checks or adjust logic to satisfy failing assertion.")
        elif primary_check.check_type == CheckType.LINT:
            suggestions.append("Fix code formatting, imports, or style violations reported by linter.")
        elif primary_check.check_type == CheckType.TYPECHECK:
            suggestions.append("Add explicit type annotations or null checks to satisfy static type analyzer.")

        return FailureAnalysisReport(
            failure_type=FailureClassification.CODE_FAILURE,
            failure_signature=current_signature,
            root_cause_summary=root_summary,
            affected_files=affected_files,
            affected_symbols=affected_symbols,
            can_retry=True,
            retry_block_reason=None,
            suggested_changes=suggestions,
        )
