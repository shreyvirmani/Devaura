"""Devaura Unified Lifecycle Observability & Audit Event Subsystem.

Provides end-to-end tracing, structured lifecycle event recording,
tool execution auditing, and cryptographic credential redaction.
"""

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LifecycleEventType(str, Enum):
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    REPAIR_CONTEXT_CREATED = "REPAIR_CONTEXT_CREATED"
    PLAN_CREATED = "PLAN_CREATED"
    PATCH_GENERATED = "PATCH_GENERATED"
    RISK_ANALYZED = "RISK_ANALYZED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVED = "APPROVED"
    PATCH_APPLIED = "PATCH_APPLIED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_PASSED = "VERIFICATION_PASSED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    RETRY_ELIGIBLE = "RETRY_ELIGIBLE"
    RETRY_STARTED = "RETRY_STARTED"
    REPAIR_EXHAUSTED = "REPAIR_EXHAUSTED"
    PR_PREPARED = "PR_PREPARED"
    PR_APPROVED = "PR_APPROVED"
    PR_CREATED = "PR_CREATED"
    SECURITY_BLOCK = "SECURITY_BLOCK"


class RedactionFilter:
    """Recursively redacts secrets, tokens, keys, and credentials from logs and events."""

    SECRET_KEY_PATTERNS = [
        re.compile(r"(?i)(token|secret|password|key|auth|credential|api[_-]?key|signature)")
    ]

    SECRET_VALUE_PATTERNS = [
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),                # GitHub Personal Tokens
        re.compile(r"pr-auth-[a-f0-9]{32,}"),                     # Devaura PR HMAC Tokens
        re.compile(r"bearer\s+[a-zA-Z0-9_\-\.=:_+/]{16,}", re.I), # Bearer tokens
        re.compile(r"-----BEGIN[ A-Z0-9_-]+KEY-----"),            # Private Keys
    ]

    @classmethod
    def redact_string(cls, value: str) -> str:
        if not value:
            return value
        redacted = value
        for pattern in cls.SECRET_VALUE_PATTERNS:
            redacted = pattern.sub("[REDACTED_SECRET]", redacted)
        return redacted

    @classmethod
    def redact_data(cls, data: Any) -> Any:
        if isinstance(data, str):
            return cls.redact_string(data)
        elif isinstance(data, dict):
            clean_dict = {}
            for k, v in data.items():
                is_secret_key = any(p.search(str(k)) for p in cls.SECRET_KEY_PATTERNS)
                if is_secret_key and isinstance(v, (str, bytes)):
                    clean_dict[k] = "[REDACTED_CREDENTIAL]"
                else:
                    clean_dict[k] = cls.redact_data(v)
            return clean_dict
        elif isinstance(data, (list, tuple)):
            return [cls.redact_data(item) for item in data]
        return data


class RepairEvent(BaseModel):
    """Unified Lifecycle Audit Event representing a key milestone transition."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repair_id: str
    trace_id: str
    investigation_id: Optional[str] = None
    verification_id: Optional[str] = None
    pr_id: Optional[str] = None
    event_type: LifecycleEventType
    stage: str
    status: str
    timestamp: datetime = Field(default_factory=utc_now)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        self.metadata = RedactionFilter.redact_data(self.metadata)


class ToolExecutionEvent(BaseModel):
    """Audit log of an individual MCP or internal tool invocation."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    repair_id: Optional[str] = None
    server: str
    tool: str
    risk_level: str
    arguments_hash: str
    result_status: str
    duration_ms: float = 0.0
    approval_requirement: bool = False
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        trace_id: str,
        server: str,
        tool: str,
        risk_level: str,
        arguments: Dict[str, Any],
        result_status: str,
        duration_ms: float,
        repair_id: Optional[str] = None,
        approval_requirement: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ToolExecutionEvent":
        safe_args = RedactionFilter.redact_data(arguments)
        args_str = json.dumps(safe_args, sort_keys=True, default=str)
        args_hash = hashlib.sha256(args_str.encode("utf-8")).hexdigest()[:16]

        return cls(
            trace_id=trace_id,
            repair_id=repair_id,
            server=server,
            tool=tool,
            risk_level=risk_level,
            arguments_hash=args_hash,
            result_status=result_status,
            duration_ms=duration_ms,
            approval_requirement=approval_requirement,
            metadata=RedactionFilter.redact_data(metadata or {}),
        )


class LifecycleTracker:
    """In-memory audit store and event publisher for Devaura execution runs."""

    def __init__(self):
        self._events: List[RepairEvent] = []
        self._tool_events: List[ToolExecutionEvent] = []

    def record_event(
        self,
        repair_id: str,
        trace_id: str,
        event_type: LifecycleEventType,
        stage: str,
        status: str,
        duration_ms: float = 0.0,
        investigation_id: Optional[str] = None,
        verification_id: Optional[str] = None,
        pr_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> RepairEvent:
        event = RepairEvent(
            repair_id=repair_id,
            trace_id=trace_id,
            investigation_id=investigation_id,
            verification_id=verification_id,
            pr_id=pr_id,
            event_type=event_type,
            stage=stage,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata or {},
            error_code=error_code,
        )
        self._events.append(event)
        return event

    def record_tool_call(
        self,
        trace_id: str,
        server: str,
        tool: str,
        risk_level: str,
        arguments: Dict[str, Any],
        result_status: str,
        duration_ms: float,
        repair_id: Optional[str] = None,
        approval_requirement: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionEvent:
        event = ToolExecutionEvent.create(
            trace_id=trace_id,
            repair_id=repair_id,
            server=server,
            tool=tool,
            risk_level=risk_level,
            arguments=arguments,
            result_status=result_status,
            duration_ms=duration_ms,
            approval_requirement=approval_requirement,
            metadata=metadata,
        )
        self._tool_events.append(event)
        return event

    def get_repair_events(self, repair_id: str) -> List[RepairEvent]:
        return [e for e in self._events if e.repair_id == repair_id]

    def get_trace_events(self, trace_id: str) -> List[RepairEvent]:
        return [e for e in self._events if e.trace_id == trace_id]

    def get_tool_events(self, trace_id: Optional[str] = None, repair_id: Optional[str] = None) -> List[ToolExecutionEvent]:
        if trace_id:
            return [t for t in self._tool_events if t.trace_id == trace_id]
        if repair_id:
            return [t for t in self._tool_events if t.repair_id == repair_id]
        return list(self._tool_events)

    def clear(self) -> None:
        self._events.clear()
        self._tool_events.clear()


# Global Singleton Tracker
tracker = LifecycleTracker()
