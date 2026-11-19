import os
from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    SECRET_KEY: str = "devaura-secret-key-at-least-32-chars-long-for-security"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./devaura.db")

    # LLM Providers
    LLM_PROVIDER: str = "gemini"  # gemini, openai, anthropic
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # GitHub Integration
    GITHUB_TOKEN: str | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None

    # MCP Protocol
    MCP_SERVER_CONFIG: str = "config/mcp_servers.json"
    MCP_CONNECT_TIMEOUT_MS: int = 15000
    MCP_TOOL_TIMEOUT_MS: int = 60000

    # Sandbox Isolation
    SANDBOX_BACKEND: str = "local"  # docker, local
    SANDBOX_IMAGE: str = "python:3.12-slim"
    SANDBOX_TIMEOUT_SECONDS: int = 120
    SANDBOX_MEMORY_LIMIT: str = "2048m"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
