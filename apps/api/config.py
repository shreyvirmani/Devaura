import os
from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_ENVIRONMENTS = {"testing", "development", "staging", "production"}
DEFAULT_DEV_SECRET_KEY = "devaura-secret-key-at-least-32-chars-long-for-security"


class Settings(BaseSettings):
    """Devaura Central Application Settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core App
    APP_NAME: str = "Devaura"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = DEFAULT_DEV_SECRET_KEY
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Security & Auth Gating
    ALLOW_DEV_USER_FALLBACK: bool = False  # Strictly forbidden in production/staging

    # Database & PostgreSQL Pool
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./devaura.db")
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_STATEMENT_TIMEOUT_MS: int = 30000

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        normalized = (v or "development").strip().lower()
        aliases = {"prod": "production", "stage": "staging", "test": "testing", "dev": "development"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in VALID_ENVIRONMENTS:
            raise ValueError(f"Invalid APP_ENV '{v}'. Must be one of: {sorted(VALID_ENVIRONMENTS)}")
        return normalized

    # LLM Providers
    LLM_PROVIDER: str = "gemini"  # gemini, openai, anthropic
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # GitHub Integration & GitHub App
    GITHUB_TOKEN: str | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    GITHUB_APP_ID: str | None = None
    GITHUB_APP_PRIVATE_KEY: str | None = None
    GITHUB_APP_CLIENT_ID: str | None = None
    GITHUB_APP_CLIENT_SECRET: str | None = None
    GITHUB_WEBHOOK_SECRET: str | None = None
    GITHUB_APP_SLUG: str = "devaura-repair"

    # MCP Protocol
    MCP_SERVER_CONFIG: str = "config/mcp_servers.json"
    MCP_CONNECT_TIMEOUT_MS: int = 15000
    MCP_TOOL_TIMEOUT_MS: int = 60000

    # Sandbox Isolation
    SANDBOX_BACKEND: str = "local"  # docker, local
    SANDBOX_IMAGE: str = "python:3.12-slim"
    SANDBOX_TIMEOUT_SECONDS: int = 120
    SANDBOX_MEMORY_LIMIT: str = "2048m"

    # Durable Worker & Job Execution (Phase 3)
    WORKER_ENABLED: bool = True
    WORKER_CONCURRENCY: int = 2
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    JOB_LEASE_DURATION_SECONDS: int = 300
    JOB_MAX_ATTEMPTS: int = 3
    INVESTIGATION_MAX_RUNTIME_SECONDS: int = 180
    WORKSPACE_MAX_CONCURRENT_JOBS: int = 3
    WORKSPACE_MAX_QUEUED_JOBS: int = 20

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_staging_or_production(self) -> bool:
        return self.APP_ENV in {"staging", "production"}

    def validate_staging_or_production(self) -> List[str]:
        """Validate fail-closed requirements for staging and production.

        Returns a list of configuration errors (empty if valid).
        """
        if not self.is_staging_or_production:
            return []

        errors: List[str] = []
        if self.ALLOW_DEV_USER_FALLBACK:
            errors.append("ALLOW_DEV_USER_FALLBACK must be false in staging/production.")
        if not self.SECRET_KEY or self.SECRET_KEY == DEFAULT_DEV_SECRET_KEY or len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be a non-default secret of at least 32 characters.")
        db_url = (self.DATABASE_URL or "").strip().lower()
        if not (db_url.startswith("postgresql://") or db_url.startswith("postgresql+asyncpg://")):
            errors.append("DATABASE_URL must use PostgreSQL (postgresql:// or postgresql+asyncpg://) in staging/production.")
        if "*" in self.cors_origins or not self.cors_origins:
            errors.append("ALLOWED_ORIGINS must explicitly list allowed origins without wildcard '*'.")
        if not self.GITHUB_APP_ID or not self.GITHUB_APP_PRIVATE_KEY or not self.GITHUB_WEBHOOK_SECRET:
            errors.append("GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, and GITHUB_WEBHOOK_SECRET are required in staging/production.")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()
