import time
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.config import get_settings
from database.connection import get_db_session

router = APIRouter(prefix="/health", tags=["Health"])
START_TIME = time.time()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str
    uptime_seconds: float


@router.get("", response_model=HealthResponse)
async def get_health(session: AsyncSession = Depends(get_db_session)) -> HealthResponse:
    """Comprehensive health check checking API and database connectivity."""
    settings = get_settings()
    db_status = "healthy"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="healthy" if "healthy" in db_status else "degraded",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database=db_status,
        uptime_seconds=round(time.time() - START_TIME, 2),
    )


@router.get("/ready", status_code=status.HTTP_200_OK)
async def get_ready(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Readiness probe for container orchestrators."""
    try:
        await session.execute(text("SELECT 1"))
        return {"ready": "true"}
    except Exception as e:
        return {"ready": "false", "reason": str(e)}


@router.get("/live", status_code=status.HTTP_200_OK)
async def get_live() -> dict[str, str]:
    """Liveness probe."""
    return {"live": "true"}
