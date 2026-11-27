import os
from typing import AsyncGenerator
from urllib.parse import urlsplit
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass

_engine: AsyncEngine | None = None
_engine_url: str | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """Retrieve the database URL from environment or fallback to SQLite."""
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./devaura.db").strip()
    # Handle standard postgresql:// prefix if provided
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def is_transaction_pooler_url(db_url: str) -> bool:
    """Return True when the asyncpg URL targets Supabase or a PgBouncer transaction pooler."""
    if "asyncpg" not in (db_url or "").lower():
        return False
    if os.getenv("DB_DISABLE_PREPARED_STATEMENTS", "").strip().lower() in {"1", "true", "yes"}:
        return True
    parsed = urlsplit(db_url)
    host = (parsed.hostname or "").lower()
    query = (parsed.query or "").lower()
    return (
        parsed.port == 6543
        or "supabase.com" in host
        or "supabase.co" in host
        or "pgbouncer=true" in query
    )


def build_asyncpg_connect_args(db_url: str, statement_timeout_ms: int = 0) -> dict:
    """Build asyncpg connect_args, disabling prepared statement caches for transaction poolers."""
    connect_args: dict = {}
    if "asyncpg" not in (db_url or "").lower():
        return connect_args
    if statement_timeout_ms > 0:
        connect_args["server_settings"] = {"statement_timeout": str(statement_timeout_ms)}
    if is_transaction_pooler_url(db_url):
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
    return connect_args


def get_engine() -> AsyncEngine:
    """Lazy initialize and return the async engine."""
    global _engine, _engine_url, _session_maker
    db_url = get_database_url()
    if _engine is None or _engine_url != db_url:
        from apps.api.config import get_settings
        settings = get_settings()
        connect_args: dict = {}
        engine_kwargs: dict = {
            "echo": os.getenv("LOG_LEVEL", settings.LOG_LEVEL).upper() == "DEBUG",
        }
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False
        else:
            stmt_timeout = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", settings.DB_STATEMENT_TIMEOUT_MS))
            connect_args = build_asyncpg_connect_args(db_url, statement_timeout_ms=stmt_timeout)
            if is_transaction_pooler_url(db_url):
                # Transaction poolers (e.g. Supabase PgBouncer) must use NullPool
                engine_kwargs["poolclass"] = NullPool
            else:
                # Direct PostgreSQL production/staging connection pool configuration
                engine_kwargs.update(
                    pool_size=int(os.getenv("DB_POOL_SIZE", settings.DB_POOL_SIZE)),
                    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", settings.DB_MAX_OVERFLOW)),
                    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", settings.DB_POOL_TIMEOUT_SECONDS)),
                    pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", settings.DB_POOL_RECYCLE_SECONDS)),
                    pool_pre_ping=True,
                )
        _engine = create_async_engine(
            db_url,
            connect_args=connect_args,
            **engine_kwargs,
        )
        _engine_url = db_url
        _session_maker = async_sessionmaker(
            _engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get the sessionmaker instance."""
    global _session_maker
    if _session_maker is None:
        get_engine()
    assert _session_maker is not None
    return _session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding transactional database sessions."""
    session_factory = get_session_maker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Alias for dependency consistency
get_db = get_db_session


async def init_db() -> None:
    """Create all database tables on application startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # SQLite lightweight schema sync for Phase 4 columns
        if "sqlite" in str(engine.url):
            def sync_columns(connection):
                cursor = connection.connection.cursor()
                try:
                    cursor.execute("PRAGMA table_info(investigations)")
                    existing_cols = {row[1] for row in cursor.fetchall()}
                    new_cols = [
                        ("title", "VARCHAR(255)"),
                        ("failure_type", "VARCHAR(50) DEFAULT 'UNKNOWN'"),
                        ("error_message", "TEXT"),
                        ("stack_trace", "TEXT"),
                        ("failed_tests", "JSON DEFAULT '[]'"),
                        ("ci_run_id", "VARCHAR(100)"),
                        ("commit_sha", "VARCHAR(64)"),
                        ("branch", "VARCHAR(100) DEFAULT 'main'"),
                        ("evidence_sufficiency", "VARCHAR(50) DEFAULT 'INSUFFICIENT'"),
                        ("workspace_id", "VARCHAR(36)"),
                    ]
                    for col_name, col_type in new_cols:
                        if col_name not in existing_cols:
                            cursor.execute(f"ALTER TABLE investigations ADD COLUMN {col_name} {col_type}")

                    cursor.execute("PRAGMA table_info(repositories)")
                    repo_cols = {row[1] for row in cursor.fetchall()}
                    new_repo_cols = [
                        ("workspace_id", "VARCHAR(36)"),
                        ("github_installation_id", "VARCHAR(36)"),
                        ("github_repository_id", "INTEGER"),
                        ("full_name", "VARCHAR(200)"),
                        ("private", "BOOLEAN DEFAULT 0"),
                        ("connection_status", "VARCHAR(30) DEFAULT 'CONNECTED'"),
                        ("permissions_snapshot", "JSON DEFAULT '{}'"),
                        ("last_webhook_received_at", "DATETIME"),
                        ("last_indexed_at", "DATETIME"),
                    ]
                    for col_name, col_type in new_repo_cols:
                        if col_name not in repo_cols:
                            cursor.execute(f"ALTER TABLE repositories ADD COLUMN {col_name} {col_type}")

                    cursor.execute("PRAGMA table_info(users)")
                    user_cols = {row[1] for row in cursor.fetchall()}
                    if "hashed_password" not in user_cols:
                        cursor.execute("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255)")
                    if "is_active" not in user_cols:
                        cursor.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
                    if "is_superuser" not in user_cols:
                        cursor.execute("ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT 0")

                    cursor.execute("PRAGMA table_info(evidence)")
                    ev_cols = {row[1] for row in cursor.fetchall()}
                    new_ev_cols = [
                        ("repository_path", "VARCHAR(500)"),
                        ("symbol_id", "VARCHAR(255)"),
                        ("line_start", "INTEGER"),
                        ("line_end", "INTEGER"),
                        ("commit_sha", "VARCHAR(64)"),
                        ("confidence", "FLOAT DEFAULT 1.0"),
                        ("relevance", "FLOAT DEFAULT 0.5"),
                    ]
                    for col_name, col_type in new_ev_cols:
                        if col_name not in ev_cols:
                            cursor.execute(f"ALTER TABLE evidence ADD COLUMN {col_name} {col_type}")

                    cursor.execute("PRAGMA table_info(repairs)")
                    rep_cols = {row[1] for row in cursor.fetchall()}
                    new_rep_cols = [
                        ("current_attempt", "INTEGER DEFAULT 1"),
                        ("max_attempts", "INTEGER DEFAULT 3"),
                        ("latest_verification_id", "VARCHAR(36)"),
                        ("workspace_id", "VARCHAR(36)"),
                    ]
                    for col_name, col_type in new_rep_cols:
                        if col_name not in rep_cols:
                            cursor.execute(f"ALTER TABLE repairs ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

            await conn.run_sync(sync_columns)


async def close_db() -> None:
    """Close the database engine."""
    global _engine, _engine_url, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _engine_url = None
        _session_maker = None
