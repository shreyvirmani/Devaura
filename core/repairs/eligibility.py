"""Devaura Phase 4 Repair Eligibility Gate.

Explicitly evaluates whether an investigated incident is eligible for
automated repair planning and patch generation.
Rejections (e.g. insufficient evidence, unsupported language, safety block)
are legitimate, auditable outcomes rather than system errors.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from database.models.incidents import Incident, IncidentStatus
from database.models.models import EvidenceSufficiency, Investigation, Repository


SENSITIVE_PATH_PATTERNS = (
    ".env",
    ".pem",
    ".key",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.yaml",
    "secrets.yml",
    "..",
)


class EligibilityDecision(BaseModel):
    """Persisted outcome of the Repair Eligibility Gate."""
    eligible: bool
    reason: str
    incident_status: IncidentStatus
    failure_classification: Optional[str] = None
    investigation_id: str
    evidence_refs: List[str] = Field(default_factory=list)
    root_cause_hypothesis: Optional[str] = None
    confidence: Optional[float] = None


def evaluate_repair_eligibility(
    incident: Incident,
    investigation: Optional[Investigation],
    repo: Optional[Repository],
) -> EligibilityDecision:
    """Determine if an investigated incident is eligible for repair."""
    inv_id = investigation.id if investigation else (incident.investigation_id or "")

    # 1. Repository state check
    if not repo:
        return EligibilityDecision(
            eligible=False,
            reason="Target repository record is missing.",
            incident_status=IncidentStatus.REPAIR_NOT_ELIGIBLE,
            failure_classification="INFRASTRUCTURE_FAILURE",
            investigation_id=inv_id,
        )

    if repo.connection_status != "CONNECTED":
        return EligibilityDecision(
            eligible=False,
            reason=f"Repository connection is '{repo.connection_status}', not CONNECTED.",
            incident_status=IncidentStatus.REPAIR_NOT_ELIGIBLE,
            failure_classification="GITHUB_FAILURE",
            investigation_id=inv_id,
        )

    # 2. Investigation completion check
    if not investigation or investigation.status != "COMPLETED":
        return EligibilityDecision(
            eligible=False,
            reason="Investigation did not reach COMPLETED state.",
            incident_status=IncidentStatus.INVESTIGATION_FAILED,
            failure_classification="REPAIR_FAILURE",
            investigation_id=inv_id,
        )

    evidence_refs = [ev.id for ev in (investigation.evidence_items or [])]
    candidates = investigation.root_cause_candidates or []
    hypothesis = (
        candidates[0].description if candidates else investigation.root_cause
    )

    # 3. Evidence sufficiency check
    if investigation.evidence_sufficiency == EvidenceSufficiency.INSUFFICIENT.value or (
        not evidence_refs and not candidates and not investigation.root_cause
    ):
        return EligibilityDecision(
            eligible=False,
            reason="Insufficient evidence to formulate an actionable repair hypothesis.",
            incident_status=IncidentStatus.INSUFFICIENT_EVIDENCE,
            investigation_id=inv_id,
            evidence_refs=evidence_refs,
            root_cause_hypothesis=hypothesis,
            confidence=investigation.confidence,
        )

    # 4. Unsupported language / non-code issue check
    meta = incident.metadata_json or {}
    if meta.get("unsupported_language") or meta.get("non_repairable_config"):
        return EligibilityDecision(
            eligible=False,
            reason="Failure involves an unsupported language or non-code configuration outside repair scope.",
            incident_status=IncidentStatus.REPAIR_NOT_ELIGIBLE,
            investigation_id=inv_id,
            evidence_refs=evidence_refs,
            root_cause_hypothesis=hypothesis,
            confidence=investigation.confidence,
        )

    # 5. Safety policy check on targeted files
    for cand in candidates:
        for path in cand.affected_files or []:
            lowered = path.lower().replace("\\", "/")
            if any(pat in lowered for pat in SENSITIVE_PATH_PATTERNS) or lowered.startswith("/"):
                return EligibilityDecision(
                    eligible=False,
                    reason=f"Target path '{path}' violates Devaura safety policy.",
                    incident_status=IncidentStatus.SAFETY_BLOCK,
                    failure_classification="SAFETY_BLOCK",
                    investigation_id=inv_id,
                    evidence_refs=evidence_refs,
                    root_cause_hypothesis=hypothesis,
                    confidence=investigation.confidence,
                )

    return EligibilityDecision(
        eligible=True,
        reason="Investigation completed with sufficient evidence and actionable root-cause hypothesis.",
        incident_status=IncidentStatus.REPAIR_PENDING,
        investigation_id=inv_id,
        evidence_refs=evidence_refs,
        root_cause_hypothesis=hypothesis,
        confidence=investigation.confidence,
    )
