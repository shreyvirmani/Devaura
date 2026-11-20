import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """Retrieve the database URL from environment or fallback to SQLite."""
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./devaura.db")
    # Handle standard postgresql:// prefix if provided
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def get_engine() -> AsyncEngine:
    """Lazy initialize and return the async engine."""
    global _engine, _session_maker
    if _engine is None:
        db_url = get_database_url()
        connect_args = {}
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False
        _engine = create_async_engine(
            db_url,
            echo=os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG",
            connect_args=connect_args,
        )
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
                    ]
                    for col_name, col_type in new_cols:
                        if col_name not in existing_cols:
                            cursor.execute(f"ALTER TABLE investigations ADD COLUMN {col_name} {col_type}")

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
                    ]
                    for col_name, col_type in new_rep_cols:
                        if col_name not in rep_cols:
                            cursor.execute(f"ALTER TABLE repairs ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

            await conn.run_sync(sync_columns)


async def close_db() -> None:
    """Close the database engine."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None
