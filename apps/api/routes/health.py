import time
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.config import get_settings
from database.connection import get_db_session

router = APIRouter(prefix="/health", tags=["Health"])
START_TIME = time.time()
EXPECTED_ALEMBIC_HEAD = "0004_phase4_repair_pipeline"


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str
    uptime_seconds: float


async def check_readiness(session: AsyncSession) -> tuple[bool, dict]:
    """Check database, migration, and environment configuration readiness without exposing secrets."""
    settings = get_settings()
    checks: dict[str, str] = {}
    ready = True

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        ready = False

    if settings.is_staging_or_production:
        config_errors = settings.validate_staging_or_production()
        if config_errors:
            checks["configuration"] = "invalid"
            ready = False
        else:
            checks["configuration"] = "ok"

        checks["github_app"] = (
            "configured"
            if (settings.GITHUB_APP_ID and settings.GITHUB_APP_PRIVATE_KEY and settings.GITHUB_WEBHOOK_SECRET)
            else "missing"
        )
        if checks["github_app"] != "configured":
            ready = False

        if checks["database"] == "ok":
            try:
                res = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                version_num = res.scalar_one_or_none()
                if version_num == EXPECTED_ALEMBIC_HEAD:
                    checks["migrations"] = "ok"
                else:
                    checks["migrations"] = "outdated_or_missing"
                    ready = False
            except Exception:
                checks["migrations"] = "unavailable"
                ready = False
    else:
        checks["configuration"] = "ok"
        checks["migrations"] = "skipped_in_non_staging"

    return ready, checks


@router.get("", response_model=HealthResponse)
async def get_health(session: AsyncSession = Depends(get_db_session)) -> HealthResponse:
    """Comprehensive health check checking API and database connectivity."""
    settings = get_settings()
    db_status = "healthy"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database=db_status,
        uptime_seconds=round(time.time() - START_TIME, 2),
    )


@router.get("/ready")
async def get_ready(response: Response, session: AsyncSession = Depends(get_db_session)) -> dict:
    """Readiness probe for container orchestrators and load balancers (returns 503 if unready)."""
    ready, checks = await check_readiness(session)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "ready": "false",
            "checks": checks,
        }
    return {"ready": "true"}


@router.get("/live", status_code=status.HTTP_200_OK)
async def get_live() -> dict[str, str]:
    """Lightweight liveness probe (does not query external dependencies)."""
    return {"live": "true"}
