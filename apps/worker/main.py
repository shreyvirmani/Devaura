"""Standalone DurableJobWorker entrypoint for independent staging/production execution.

Run with:
    python -m apps.worker.main
"""

from __future__ import annotations

import asyncio
import signal
import sys

from apps.api.config import get_settings
from apps.api.logger import logger
from core.jobs.worker import DurableJobWorker
from database.connection import close_db, init_db


async def run_worker_process() -> None:
    """Validate configuration, run DurableJobWorker until SIGINT/SIGTERM, and close DB."""
    settings = get_settings()
    logger.info(
        "Starting standalone Devaura DurableJobWorker",
        extra={
            "component": "worker_main",
            "event": "startup",
            "env": settings.APP_ENV,
            "poll_interval": settings.WORKER_POLL_INTERVAL_SECONDS,
            "lease_seconds": settings.JOB_LEASE_DURATION_SECONDS,
        },
    )

    if settings.is_staging_or_production:
        errors = settings.validate_staging_or_production()
        if errors:
            raise RuntimeError("Staging/Production fail-closed worker configuration error(s): " + "; ".join(errors))
    else:
        await init_db()

    worker = DurableJobWorker()
    stop_event = asyncio.Event()

    def _request_shutdown(*_args) -> None:
        logger.info("Worker received shutdown signal", extra={"component": "worker_main", "event": "shutdown_signal"})
        worker.stop()
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except NotImplementedError:
            # Windows ProactorEventLoop fallback
            signal.signal(sig, _request_shutdown)

    worker_task = asyncio.create_task(worker.run_loop())
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    finally:
        worker.stop()
        await close_db()
        logger.info("Standalone DurableJobWorker stopped cleanly", extra={"component": "worker_main", "event": "stopped"})


def main() -> int:
    try:
        asyncio.run(run_worker_process())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logger.error(f"Worker exited with fatal error: {exc}", extra={"component": "worker_main", "event": "fatal"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
