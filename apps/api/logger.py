import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional


SECRET_PATTERNS = [
    re.compile(r"(ghp_[a-zA-Z0-9]{36})"),
    re.compile(r"(gho_[a-zA-Z0-9]{36})"),
    re.compile(r"(github_pat_[a-zA-Z0-9_]{82})"),
    re.compile(r"(AIzaSy[a-zA-Z0-9_\-]{33})"),
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),
    re.compile(r"(bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"'])([^\"']+)([\"'])", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Mask credentials and API tokens from log output."""
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON without leaking stdout for MCP stdio compatibility."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "event": getattr(record, "event", record.getMessage()),
            "status": getattr(record, "status", "info"),
        }

        # Optional structured context fields
        if hasattr(record, "request_id"):
            log_payload["request_id"] = record.request_id
        if hasattr(record, "investigation_id"):
            log_payload["investigation_id"] = record.investigation_id
        if hasattr(record, "duration_ms"):
            log_payload["duration_ms"] = record.duration_ms
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload["data"] = record.extra_data

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        raw_json = json.dumps(log_payload, default=str)
        return redact_secrets(raw_json)


def setup_logger(name: str = "devaura", level: str = "INFO") -> logging.Logger:
    """Configures structured logger routing strictly to stderr."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # Remove existing handlers to avoid duplicates
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    # Route logs strictly to stderr so MCP stdio messages are never corrupted
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(StructuredJsonFormatter())
    logger.addHandler(stream_handler)

    return logger


# Default application logger instance
logger = setup_logger("devaura")
