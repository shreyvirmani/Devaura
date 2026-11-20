"""Devaura Patch Risk Analyzer.

Performs static analysis of proposed unified diffs across 5 safety dimensions:
1. Structural Risk (lines changed, files modified, deletions)
2. Behavioral Risk (auth, crypto, database migrations)
3. Test Coverage Risk (test deletion or modification)
4. Evidence Scope Risk (unsupported file modification)
5. Security Risk (dangerous functions, shell execution, secrets)
"""

import re
from typing import List
from agent.repair.models import (
    PatchResult,
    PatchRisk,
    PatchRiskFinding,
    PatchRiskLevel,
    RepairContext,
    RepairPlan,
)


class PatchRiskAnalyzer:
    """Calculates multi-dimensional risk metrics for proposed code patches."""

    DANGEROUS_SECURITY_PATTERNS = [
        (r"\beval\s*\(", "Use of 'eval()' is strictly forbidden."),
        (r"\bexec\s*\(", "Use of 'exec()' is strictly forbidden."),
        (r"os\.system\s*\(", "Direct invocation of 'os.system()' is dangerous."),
        (r"subprocess\..*shell\s*=\s*True", "Shell execution with 'shell=True' is dangerous."),
        (r"\bpickle\.loads\s*\(", "Unpickling untrusted data is unsafe."),
        (r"(?i)(password|secret|api_key|token)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Possible hardcoded secret in patch."),
    ]

    SENSITIVE_BEHAVIORAL_KEYWORDS = [
        "auth", "login", "password", "jwt", "crypto", "encryption", "migration", "token", "session"
    ]

    def __init__(self):
        pass

    def analyze(
        self,
        patch: PatchResult,
        plan: RepairPlan,
        context: RepairContext,
    ) -> PatchRisk:
        """Perform comprehensive static risk analysis on the patch diff."""
        findings: List[PatchRiskFinding] = []
        blocking_findings: List[str] = []
        risk_score: float = 0.0

        diff = patch.unified_diff
        changed_files = patch.changed_files
        lines_added = patch.lines_added
        lines_removed = patch.lines_removed

        # -------------------------------------------------------------
        # 1. Structural Risk
        # -------------------------------------------------------------
        total_churn = lines_added + lines_removed
        if total_churn > 100:
            msg = f"High code churn: {total_churn} lines changed (threshold: 100)."
            findings.append(PatchRiskFinding(category="STRUCTURAL", description=msg, is_blocking=False, severity="HIGH"))
            risk_score += 0.35
        elif total_churn > 50:
            msg = f"Moderate code churn: {total_churn} lines changed."
            findings.append(PatchRiskFinding(category="STRUCTURAL", description=msg, is_blocking=False, severity="MEDIUM"))
            risk_score += 0.20
        else:
            risk_score += 0.05

        if len(changed_files) > 3:
            msg = f"Broad file scope: {len(changed_files)} files modified (threshold: 3)."
            findings.append(PatchRiskFinding(category="STRUCTURAL", description=msg, is_blocking=False, severity="HIGH"))
            risk_score += 0.25

        # -------------------------------------------------------------
        # 2. Evidence Scope Risk
        # -------------------------------------------------------------
        evidenced_files = set(context.affected_files)
        for cf in changed_files:
            if cf not in evidenced_files:
                msg = f"Unevidenced file modified: '{cf}' was not identified in Phase 4 investigation."
                findings.append(PatchRiskFinding(category="EVIDENCE_SCOPE", description=msg, is_blocking=True, severity="CRITICAL"))
                blocking_findings.append(msg)
                risk_score += 0.50

        # -------------------------------------------------------------
        # 3. Behavioral Risk (Auth, Crypto, Migrations)
        # -------------------------------------------------------------
        for cf in changed_files:
            cf_lower = cf.lower()
            if any(k in cf_lower for k in self.SENSITIVE_BEHAVIORAL_KEYWORDS):
                msg = f"Modification to sensitive behavioral subsystem in file: '{cf}'."
                findings.append(PatchRiskFinding(category="BEHAVIORAL", description=msg, is_blocking=False, severity="HIGH"))
                risk_score += 0.25

        # -------------------------------------------------------------
        # 4. Test Coverage Risk (e.g. Deleting tests)
        # -------------------------------------------------------------
        for line in diff.splitlines():
            if line.startswith("--- a/") and ("test_" in line or "_test" in line):
                # Checking if test lines are being removed
                pass
            if line.startswith("-") and not line.startswith("---"):
                # Test deletion check
                if "def test_" in line or "it(" in line or "describe(" in line:
                    msg = f"Dangerous test deletion detected: '{line.strip()}'."
                    findings.append(PatchRiskFinding(category="TEST_COVERAGE", description=msg, is_blocking=True, severity="CRITICAL"))
                    blocking_findings.append(msg)
                    risk_score += 0.40

        # -------------------------------------------------------------
        # 5. Security Risk (Malicious or dangerous functions)
        # -------------------------------------------------------------
        added_lines = "\n".join(
            line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
        )

        for pattern, description in self.DANGEROUS_SECURITY_PATTERNS:
            if re.search(pattern, added_lines):
                findings.append(PatchRiskFinding(category="SECURITY", description=description, is_blocking=True, severity="CRITICAL"))
                blocking_findings.append(description)
                risk_score += 0.60

        # Determine level
        risk_score = min(1.0, max(0.0, risk_score))
        if blocking_findings or risk_score >= 0.70:
            level = PatchRiskLevel.CRITICAL
        elif risk_score >= 0.40:
            level = PatchRiskLevel.HIGH
        elif risk_score >= 0.20:
            level = PatchRiskLevel.MEDIUM
        else:
            level = PatchRiskLevel.LOW

        rationale = (
            f"Risk Level: {level.value}. {len(findings)} finding(s), {len(blocking_findings)} blocking issue(s). "
            f"Risk score: {risk_score:.2f}."
        )

        return PatchRisk(
            score=risk_score,
            level=level,
            findings=findings,
            blocking_findings=blocking_findings,
            rationale=rationale,
        )
