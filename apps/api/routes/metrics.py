from datetime import datetime
from typing import Any, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.auth import CurrentUser, get_current_user
from database.connection import get_db_session
from database.models import (
    CheckStatus,
    Investigation,
    PullRequest,
    RepairAttempt,
    ToolExecution,
    VerificationRun,
)

router = APIRouter(tags=["Metrics & Observability"])


class PlatformMetrics(BaseModel):
    total_investigations: int
    active_investigations: int
    total_repairs: int
    successful_repairs: int
    failed_repairs: int
    repair_success_rate_pct: float
    verification_pass_rate_pct: float
    total_pull_requests_created: int
    total_mcp_tool_calls: int


class ToolExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str | None
    server: str
    tool: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    status: str
    latency_ms: float
    created_at: datetime


@router.get("/metrics", response_model=PlatformMetrics)
async def get_platform_metrics(
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> PlatformMetrics:
    """Retrieve platform observability metrics."""
    # Count investigations
    inv_count = await session.scalar(select(func.count(Investigation.id))) or 0
    active_inv = await session.scalar(
        select(func.count(Investigation.id)).where(
            Investigation.status.in_(["INVESTIGATING", "DIAGNOSED", "PLAN_READY", "REPAIRING", "VERIFYING"])
        )
    ) or 0

    # Count repairs
    total_repairs = await session.scalar(select(func.count(RepairAttempt.id))) or 0
    successful_repairs = await session.scalar(
        select(func.count(RepairAttempt.id)).where(RepairAttempt.status == "verified")
    ) or 0
    failed_repairs = await session.scalar(
        select(func.count(RepairAttempt.id)).where(RepairAttempt.status == "failed")
    ) or 0

    # Verification runs
    total_verifications = await session.scalar(select(func.count(VerificationRun.id))) or 0
    passed_verifications = await session.scalar(
        select(func.count(VerificationRun.id)).where(VerificationRun.test_status == CheckStatus.PASSED.value)
    ) or 0

    # PRs and MCP tool calls
    total_prs = await session.scalar(select(func.count(PullRequest.id))) or 0
    total_tool_calls = await session.scalar(select(func.count(ToolExecution.id))) or 0

    success_rate = (successful_repairs / total_repairs * 100.0) if total_repairs > 0 else 0.0
    verif_rate = (passed_verifications / total_verifications * 100.0) if total_verifications > 0 else 0.0

    return PlatformMetrics(
        total_investigations=inv_count,
        active_investigations=active_inv,
        total_repairs=total_repairs,
        successful_repairs=successful_repairs,
        failed_repairs=failed_repairs,
        repair_success_rate_pct=round(success_rate, 1),
        verification_pass_rate_pct=round(verif_rate, 1),
        total_pull_requests_created=total_prs,
        total_mcp_tool_calls=total_tool_calls,
    )


@router.get("/executions", response_model=List[ToolExecutionResponse])
async def list_tool_executions(
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[ToolExecutionResponse]:
    """Retrieve recent MCP tool execution audit trace records."""
    result = await session.execute(
        select(ToolExecution).order_by(ToolExecution.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
