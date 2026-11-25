"""Devaura Production Structured Audit Logger.

Provides append-only persistence of security, tenant, and lifecycle events
with recursive secret redaction.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.logger import logger, redact_secrets
from database.models import AuditEventRecord


def sanitize_audit_metadata(data: Any) -> Any:
    """Recursively scrub secrets, tokens, and passwords from audit metadata."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            # Never record sensitive credential fields
            if any(term in k.lower() for term in ("token", "password", "secret", "key", "authorization", "cookie")):
                sanitized[k] = "[REDACTED_CREDENTIAL]"
            else:
                sanitized[k] = sanitize_audit_metadata(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_audit_metadata(item) for item in data]
    elif isinstance(data, str):
        return redact_secrets(data)
    return data


async def record_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    outcome: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditEventRecord:
    """Persist an append-only audit event with recursive secret redaction."""
    clean_details = sanitize_audit_metadata(details or {})

    audit = AuditEventRecord(
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        details=clean_details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit)
    await db.flush()

    logger.info(
        f"[AUDIT] {action} on {resource_type}:{resource_id or 'none'} -> {outcome}",
        extra={
            "component": "audit_trail",
            "audit_action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "outcome": outcome,
        },
    )
    return audit
