"""Devaura GitHub Webhook Ingestion & Event Processing.

Handles:
1. HMAC-SHA256 signature verification (X-Hub-Signature-256).
2. Delivery ID validation & idempotency/replay-resistance (X-GitHub-Delivery).
3. Installation lifecycle updates (installation.deleted, installation_repositories.removed).
4. Repository event tracking (push, workflow_run, check_run, pull_request) without triggering un-gated repairs.
5. Tamper-evident webhook event logging & auditing.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.logger import logger
from database.connection import get_db
from database.models import (
    AuditEventRecord,
    GitHubAppInstallation,
    Repository,
    WebhookEventRecord,
)
from integrations.github.app_service import get_github_app_service

router = APIRouter(prefix="/github/webhooks", tags=["GitHub Webhooks"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_github_webhook(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """Public webhook receiver for verified GitHub App events."""
    raw_body = await request.body()
    service = get_github_app_service()

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    # 1. Verify HMAC-SHA256 Signature
    if not x_hub_signature_256:
        # Reject missing signature
        audit = AuditEventRecord(
            workspace_id=None,
            actor_id=None,
            actor_email=None,
            action="github.webhook.rejected",
            resource_type="webhook",
            resource_id=x_github_delivery,
            outcome="DENIED",
            details={"reason": "MISSING_SIGNATURE", "ip": client_ip},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MISSING_SIGNATURE", "message": "X-Hub-Signature-256 header missing."}},
        )

    if not service.verify_webhook_signature(raw_body, x_hub_signature_256):
        # Reject invalid signature
        audit = AuditEventRecord(
            workspace_id=None,
            actor_id=None,
            actor_email=None,
            action="github.webhook.rejected",
            resource_type="webhook",
            resource_id=x_github_delivery,
            outcome="DENIED",
            details={"reason": "INVALID_SIGNATURE", "ip": client_ip},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_SIGNATURE", "message": "Webhook signature verification failed."}},
        )

    # 2. Verify Delivery ID Header
    if not x_github_delivery:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MISSING_DELIVERY_ID", "message": "X-GitHub-Delivery header missing."}},
        )

    # 3. Idempotency & Replay Resistance
    existing_stmt = select(WebhookEventRecord).where(
        WebhookEventRecord.delivery_id == x_github_delivery
    )
    existing_res = await db.execute(existing_stmt)
    existing_event = existing_res.scalar_one_or_none()

    if existing_event:
        logger.info(
            f"Duplicate webhook delivery detected: {x_github_delivery}",
            extra={"component": "webhook", "delivery_id": x_github_delivery},
        )
        audit = AuditEventRecord(
            workspace_id=existing_event.workspace_id,
            actor_id=None,
            actor_email=None,
            action="github.webhook.duplicate",
            resource_type="webhook",
            resource_id=x_github_delivery,
            outcome="SUCCESS",
            details={"delivery_id": x_github_delivery, "event": x_github_event},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        db.add(audit)
        await db.commit()

        response.status_code = status.HTTP_200_OK
        return {
            "status": "already_processed",
            "delivery_id": x_github_delivery,
            "processed_at": existing_event.processed_at.isoformat() if existing_event.processed_at else None,
        }

    # 4. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_JSON", "message": f"Malformed JSON payload: {e}"}},
        )

    event_type = x_github_event or "unknown"

    # Ping event
    if event_type == "ping":
        webhook_rec = WebhookEventRecord(
            delivery_id=x_github_delivery,
            event_type="ping",
            payload=payload,
            status="RECEIVED",
            signature_verified=True,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(webhook_rec)
        await db.commit()
        response.status_code = status.HTTP_200_OK
        return {"status": "pong", "zen": payload.get("zen")}

    # 5. Resolve Installation and Workspace
    installation_id_header = payload.get("installation", {}).get("id")
    target_installation: Optional[GitHubAppInstallation] = None
    target_workspace_id: Optional[str] = None
    target_repo_id: Optional[str] = None

    if installation_id_header:
        inst_stmt = select(GitHubAppInstallation).where(
            GitHubAppInstallation.installation_id == int(installation_id_header)
        )
        inst_res = await db.execute(inst_stmt)
        target_installation = inst_res.scalar_one_or_none()
        if target_installation:
            target_workspace_id = target_installation.workspace_id

    # 6. Lifecycle Events
    action = payload.get("action", "")

    if event_type == "installation":
        if action in ("deleted", "suspend") and target_installation:
            target_installation.is_active = False
            target_installation.updated_at = datetime.now(timezone.utc)
            # Revoke repo access
            repo_update_stmt = select(Repository).where(
                Repository.github_installation_id == target_installation.id
            )
            repo_update_res = await db.execute(repo_update_stmt)
            for r in repo_update_res.scalars().all():
                r.connection_status = "ACCESS_REVOKED"
                r.updated_at = datetime.now(timezone.utc)

    elif event_type == "installation_repositories":
        if action == "removed" and target_installation:
            removed_repos = payload.get("repositories_removed", [])
            removed_ids = [r.get("id") for r in removed_repos if r.get("id")]
            if removed_ids:
                repo_update_stmt = select(Repository).where(
                    Repository.github_installation_id == target_installation.id,
                    Repository.github_repository_id.in_(removed_ids),
                )
                repo_update_res = await db.execute(repo_update_stmt)
                for r in repo_update_res.scalars().all():
                    r.connection_status = "ACCESS_REVOKED"
                    r.updated_at = datetime.now(timezone.utc)

    # 7. Repository Activity Tracking
    repo_payload = payload.get("repository")
    if repo_payload and isinstance(repo_payload, dict):
        gh_repo_id = repo_payload.get("id")
        gh_repo_full_name = repo_payload.get("full_name")

        repo_lookup_stmt = select(Repository).where(
            (Repository.github_repository_id == gh_repo_id) |
            (Repository.full_name == gh_repo_full_name)
        )
        if target_workspace_id:
            repo_lookup_stmt = repo_lookup_stmt.where(Repository.workspace_id == target_workspace_id)

        repo_res = await db.execute(repo_lookup_stmt)
        matched_repo = repo_res.scalar_one_or_none()

        if matched_repo:
            target_repo_id = matched_repo.id
            if not target_workspace_id:
                target_workspace_id = matched_repo.workspace_id
            matched_repo.last_webhook_received_at = datetime.now(timezone.utc)

    # 8. Record Webhook Ingestion
    webhook_rec = WebhookEventRecord(
        delivery_id=x_github_delivery,
        event_type=event_type,
        installation_id=target_installation.id if target_installation else None,
        workspace_id=target_workspace_id,
        repository_id=target_repo_id,
        payload=payload,
        status="RECEIVED",
        signature_verified=True,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(webhook_rec)

    # 9. Audit Event
    audit = AuditEventRecord(
        workspace_id=target_workspace_id,
        actor_id=None,
        actor_email=None,
        action="github.webhook.received",
        resource_type="webhook",
        resource_id=x_github_delivery,
        outcome="SUCCESS",
        details={
            "delivery_id": x_github_delivery,
            "event": event_type,
            "action": action,
            "repository_id": target_repo_id,
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "received",
        "event": event_type,
        "delivery_id": x_github_delivery,
        "workspace_id": target_workspace_id,
        "repository_id": target_repo_id,
    }
