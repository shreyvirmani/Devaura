"""Devaura GitHub Event Normalization Layer.

Converts raw verified GitHub webhook payloads into strongly-typed
NormalizedEvent and IncidentCandidate structures.
Business logic and incident creation must never consume raw webhook JSON directly.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from database.models.incidents import IncidentSource, IncidentType


class IncidentCandidate(BaseModel):
    """Normalized candidate ready for idempotent Incident persistence."""
    source: IncidentSource
    incident_type: IncidentType
    external_event_id: str
    external_run_id: Optional[str] = None
    external_check_id: Optional[str] = None
    dedup_key: str
    title: str
    summary: str
    failure_signature: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    workflow_name: Optional[str] = None
    workflow_run_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizedEvent(BaseModel):
    """Canonical representation of an ingested external event."""
    delivery_id: str
    event_type: str
    action: str = ""
    installation_id: Optional[int] = None
    github_repository_id: Optional[int] = None
    repository_full_name: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    conclusion: Optional[str] = None
    is_failure: bool = False
    incident_candidate: Optional[IncidentCandidate] = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventNormalizer:
    """Deterministic normalizer for supported GitHub webhook event types."""

    SUPPORTED_EVENTS = {
        "workflow_run",
        "check_run",
        "push",
        "pull_request",
        "installation",
        "installation_repositories",
        "ping",
    }

    FAILURE_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}

    @classmethod
    def normalize(
        cls,
        event_type: str,
        delivery_id: str,
        payload: Dict[str, Any],
        repository_id: Optional[str] = None,
    ) -> NormalizedEvent:
        """Normalize a raw GitHub webhook payload into a NormalizedEvent."""
        action = str(payload.get("action") or "")
        inst_id = None
        if isinstance(payload.get("installation"), dict):
            inst_id = payload["installation"].get("id")

        gh_repo_id = None
        repo_full_name = None
        if isinstance(payload.get("repository"), dict):
            gh_repo_id = payload["repository"].get("id")
            repo_full_name = payload["repository"].get("full_name")

        normalized = NormalizedEvent(
            delivery_id=delivery_id,
            event_type=event_type,
            action=action,
            installation_id=int(inst_id) if inst_id is not None else None,
            github_repository_id=int(gh_repo_id) if gh_repo_id is not None else None,
            repository_full_name=repo_full_name,
        )

        if event_type == "workflow_run":
            cls._normalize_workflow_run(normalized, payload, repository_id)
        elif event_type == "check_run":
            cls._normalize_check_run(normalized, payload, repository_id)
        elif event_type == "push":
            ref = str(payload.get("ref") or "")
            normalized.branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref or None
            normalized.commit_sha = payload.get("after")
        elif event_type == "pull_request":
            pr = payload.get("pull_request") or {}
            head = pr.get("head") or {}
            normalized.branch = head.get("ref")
            normalized.commit_sha = head.get("sha")

        return normalized

    @classmethod
    def _normalize_workflow_run(
        cls,
        normalized: NormalizedEvent,
        payload: Dict[str, Any],
        repository_id: Optional[str],
    ) -> None:
        wr = payload.get("workflow_run") or {}
        if not isinstance(wr, dict):
            return

        conclusion = str(wr.get("conclusion") or "").lower()
        normalized.conclusion = conclusion or None
        normalized.commit_sha = wr.get("head_sha")
        normalized.branch = wr.get("head_branch")

        if normalized.action == "completed" and conclusion in cls.FAILURE_CONCLUSIONS:
            normalized.is_failure = True
            run_id = str(wr.get("id") or "")
            if not run_id or not repository_id:
                return

            workflow_name = str(wr.get("name") or "GitHub Workflow")
            html_url = wr.get("html_url")
            run_number = wr.get("run_number")
            title = f"CI Failure: {workflow_name}" + (f" (#{run_number})" if run_number else "")
            summary = (
                f"GitHub workflow '{workflow_name}' completed with conclusion '{conclusion}' "
                f"on branch '{normalized.branch or 'unknown'}' (commit { (normalized.commit_sha or '')[:8] })."
            )
            failure_sig = f"workflow_run:{workflow_name}:{conclusion}"

            normalized.incident_candidate = IncidentCandidate(
                source=IncidentSource.GITHUB_WORKFLOW_RUN,
                incident_type=IncidentType.CI_FAILURE,
                external_event_id=normalized.delivery_id,
                external_run_id=run_id,
                dedup_key=f"{repository_id}:workflow_run:{run_id}",
                title=title[:255],
                summary=summary,
                failure_signature=failure_sig[:255],
                commit_sha=normalized.commit_sha,
                branch=normalized.branch,
                workflow_name=workflow_name[:200],
                workflow_run_url=html_url,
                metadata={
                    "event": "workflow_run",
                    "action": normalized.action,
                    "conclusion": conclusion,
                    "run_number": run_number,
                    "attempt": wr.get("run_attempt"),
                },
            )

    @classmethod
    def _normalize_check_run(
        cls,
        normalized: NormalizedEvent,
        payload: Dict[str, Any],
        repository_id: Optional[str],
    ) -> None:
        cr = payload.get("check_run") or {}
        if not isinstance(cr, dict):
            return

        conclusion = str(cr.get("conclusion") or "").lower()
        normalized.conclusion = conclusion or None
        normalized.commit_sha = cr.get("head_sha")
        check_suite = cr.get("check_suite") or {}
        normalized.branch = check_suite.get("head_branch") if isinstance(check_suite, dict) else None

        if normalized.action == "completed" and conclusion in cls.FAILURE_CONCLUSIONS:
            normalized.is_failure = True
            check_id = str(cr.get("id") or "")
            if not check_id or not repository_id:
                return

            check_name = str(cr.get("name") or "GitHub Check")
            html_url = cr.get("html_url")
            output = cr.get("output") or {}
            output_title = output.get("title") if isinstance(output, dict) else None
            output_summary = output.get("summary") if isinstance(output, dict) else None

            title = f"Check Failure: {check_name}"
            summary = output_summary or output_title or (
                f"GitHub check '{check_name}' completed with conclusion '{conclusion}'."
            )
            failure_sig = f"check_run:{check_name}:{conclusion}"

            normalized.incident_candidate = IncidentCandidate(
                source=IncidentSource.GITHUB_CHECK_RUN,
                incident_type=IncidentType.CHECK_FAILURE,
                external_event_id=normalized.delivery_id,
                external_check_id=check_id,
                dedup_key=f"{repository_id}:check_run:{check_id}",
                title=title[:255],
                summary=summary,
                failure_signature=failure_sig[:255],
                commit_sha=normalized.commit_sha,
                branch=normalized.branch,
                workflow_name=check_name[:200],
                workflow_run_url=html_url,
                metadata={
                    "event": "check_run",
                    "action": normalized.action,
                    "conclusion": conclusion,
                    "check_suite_id": check_suite.get("id") if isinstance(check_suite, dict) else None,
                },
            )
