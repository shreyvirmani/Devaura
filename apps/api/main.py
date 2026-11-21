import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from apps.api.config import get_settings
from apps.api.logger import logger
from apps.api.routes import code_intelligence, evaluation, health, investigations, mcp_servers, metrics, repositories, repairs, pull_requests
from database.connection import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    settings = get_settings()
    logger.info(
        "Starting Devaura API backend",
        extra={
            "component": "lifespan",
            "event": "startup",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
        },
    )
    # Initialize database tables
    await init_db()
    logger.info("Database initialized successfully", extra={"component": "database", "event": "init_db"})
    yield
    # Shutdown
    logger.info("Shutting down Devaura API", extra={"component": "lifespan", "event": "shutdown"})
    await close_db()


settings = get_settings()

app = FastAPI(
    title="Devaura API",
    description="MCP-Native AI Software Repair & Maintenance Platform Backend",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_and_latency_middleware(request: Request, call_next):
    """Logs every HTTP request with request ID, latency, and status code."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()
    
    response = await call_next(request)
    
    duration_ms = round((time.time() - start_time) * 1000.0, 2)
    response.headers["X-Request-ID"] = request_id
    
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
        extra={
            "component": "http_middleware",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


# Include API v1 Routers
api_v1_prefix = "/api/v1"
app.include_router(health.router, prefix=api_v1_prefix)
app.include_router(repositories.router, prefix=api_v1_prefix)
app.include_router(investigations.router, prefix=api_v1_prefix)
app.include_router(repairs.router, prefix=api_v1_prefix)
app.include_router(mcp_servers.router, prefix=api_v1_prefix)
app.include_router(code_intelligence.router, prefix=api_v1_prefix)
app.include_router(metrics.router, prefix=api_v1_prefix)
app.include_router(pull_requests.router, prefix=api_v1_prefix)
app.include_router(evaluation.router, prefix=api_v1_prefix)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "tagline": "Devaura — From failure to verified fix.",
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
    }
