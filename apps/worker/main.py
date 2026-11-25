"""Standalone DurableJobWorker entrypoint for independent staging/production execution.

Run with:
    python -m apps.worker.main
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys

from apps.api.config import get_settings
from apps.api.logger import logger
from core.jobs.worker import DurableJobWorker
from database.connection import close_db, init_db


async def _start_free_staging_health_server() -> asyncio.AbstractServer | None:
    """Isolated free-staging adapter: minimal HTTP /healthz listener for Render Free Web Service.

    Active ONLY when FREE_STAGING_HTTP_HEALTH=true. Production workers never bind an HTTP port.
    """
    if os.getenv("FREE_STAGING_HTTP_HEALTH", "false").lower() not in {"1", "true", "yes"}:
        return None

    port = int(os.getenv("PORT", "10000"))

    async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await asyncio.wait_for(reader.read(1024), timeout=2.0)
            body = json.dumps({"status": "alive", "mode": "free-staging-worker"}).encode("utf-8")
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + body
            )
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(_handle_client, host="0.0.0.0", port=port)
    logger.info(
        f"Free-staging worker HTTP health adapter listening on port {port}",
        extra={"component": "worker_main", "event": "free_staging_health_started", "port": port},
    )
    return server


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

    health_server = await _start_free_staging_health_server()
    worker_task = asyncio.create_task(worker.run_loop())
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    finally:
        worker.stop()
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
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
