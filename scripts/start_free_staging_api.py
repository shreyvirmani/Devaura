"""Free-staging API startup script for Render Free Web Services.

Render Free Web Services do not support `preDeployCommand`. This script runs
`alembic upgrade head` before starting Uvicorn and aborts startup immediately
if migrations fail.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable, Optional


def run_alembic_upgrade() -> None:
    """Execute `alembic upgrade head` and fail immediately on any error."""
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL must be set before starting free-staging API.")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


def start_uvicorn_server() -> None:
    """Start the FastAPI application via Uvicorn on 0.0.0.0:$PORT."""
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=port)


def run_migrations_and_start_api(
    migration_fn: Optional[Callable[[], None]] = None,
    server_fn: Optional[Callable[[], None]] = None,
) -> None:
    """Run Alembic migrations first; only start Uvicorn if migrations succeed."""
    (migration_fn or run_alembic_upgrade)()
    (server_fn or start_uvicorn_server)()


def main() -> int:
    try:
        run_migrations_and_start_api()
        return 0
    except Exception as exc:
        print(f"[start_free_staging_api] Aborting API startup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
