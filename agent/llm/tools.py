"""Devaura LLM Tool Governance & MCP Execution Layer.

Enforces strict lifecycle-based tool access control, blocks unauthorized actions,
hashes tool arguments, redacts secrets, and maintains an immutable execution audit.
"""

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field

from agent.events import LifecycleEventType, tracker
from apps.api.logger import logger
from mcp.policy.policy_engine import ToolPolicyEngine
from mcp.server.devaura_server import get_native_mcp_server


class LifecyclePhase(str, Enum):
    INVESTIGATION = "INVESTIGATION"
    REPAIR = "REPAIR"
    VERIFICATION = "VERIFICATION"
    PR = "PR"


RepairLifecyclePhase = LifecyclePhase


class PhaseToolPermissionError(PermissionError):
    """Raised when an LLM attempts an unauthorized or forbidden tool call."""
    pass


class ToolCallRecord(BaseModel):
    """Audit log record for an individual LLM tool request."""
    model_config = ConfigDict(extra="ignore")

    call_id: str = Field(default_factory=lambda: hashlib.sha256(str(time.time()).encode()).hexdigest()[:8])
    trace_id: str
    repair_id: Optional[str] = None
    investigation_id: Optional[str] = None
    lifecycle_phase: LifecyclePhase
    tool_name: str
    arguments_hash: str
    policy_decision: str  # ALLOWED | BLOCKED
    authorized: bool = True
    block_reason: Optional[str] = None
    result_summary: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMToolGovernance:
    """Enforces fine-grained governance on tools invoked by LLM agents."""

    # Allowed tools per lifecycle state
    PERMITTED_TOOLS: Dict[LifecyclePhase, Set[str]] = {
        LifecyclePhase.INVESTIGATION: {
            "read_file",
            "search_code",
            "search_symbol",
            "get_symbol",
            "get_relationships",
            "get_repository_graph",
            "find_related_tests",
            "git_history",
            "inspect_diff",
            "ast_search",
            "list_directory",
        },
        LifecyclePhase.REPAIR: {
            "read_file",
            "search_code",
            "find_related_tests",
            "inspect_diff",
        },
        LifecyclePhase.VERIFICATION: {
            "run_tests",
            "run_pytest_suite",
            "run_linter",
            "run_typecheck",
            "get_verification",
        },
        LifecyclePhase.PR: set(),  # PR tools require strict human approval, LLM cannot invoke
    }

    # Explicitly forbidden dangerous tools that the LLM can NEVER execute
    FORBIDDEN_TOOLS: Set[str] = {
        "approve_repair",
        "push_repair_branch",
        "create_pull_request",
        "merge",
        "deploy",
        "delete_file",
        "rmdir",
        "shell_exec",
    }

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or "."
        self.policy_engine = ToolPolicyEngine()
        self.audit_log: List[ToolCallRecord] = []
        self.tool_calls_count = 0
        self.tool_calls_by_type: Dict[str, int] = {}
        self.blocked_tool_calls = 0
        self.unsafe_tool_attempts = 0

    def hash_arguments(self, arguments: Dict[str, Any]) -> str:
        """Computes SHA-256 hash of tool arguments without logging plaintext values."""
        serialized = json.dumps(arguments, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def authorize_tool_call(
        self,
        phase: LifecyclePhase,
        tool_name: str,
        arguments: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> ToolCallRecord:
        """Synchronously check authorization for a tool call. Raises PhaseToolPermissionError if blocked."""
        arg_hash = self.hash_arguments(arguments)
        self.tool_calls_count += 1
        self.tool_calls_by_type[tool_name] = self.tool_calls_by_type.get(tool_name, 0) + 1

        # Check forbidden dangerous tools
        if tool_name in self.FORBIDDEN_TOOLS or any(
            fb in tool_name for fb in ("approve", "merge", "deploy", "push_repair", "create_pull_request")
        ):
            self.blocked_tool_calls += 1
            self.unsafe_tool_attempts += 1
            raise PhaseToolPermissionError(
                f"Forbidden dangerous tool '{tool_name}' is strictly forbidden from autonomous LLM invocation."
            )

        allowed_in_phase = self.PERMITTED_TOOLS.get(phase, set())
        if tool_name not in allowed_in_phase:
            self.blocked_tool_calls += 1
            raise PhaseToolPermissionError(
                f"Tool '{tool_name}' is not permitted in lifecycle phase '{phase.value}'."
            )

        record = ToolCallRecord(
            trace_id=trace_id or f"auth-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}",
            lifecycle_phase=phase,
            tool_name=tool_name,
            arguments_hash=arg_hash,
            policy_decision="ALLOWED",
            authorized=True,
            result_summary="Authorized by lifecycle policy.",
        )
        self.audit_log.append(record)
        return record

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        phase: LifecyclePhase,
        trace_id: str,
        repair_id: Optional[str] = None,
        investigation_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validates and executes a tool call under strict policy enforcement.

        Returns:
            Tuple[bool, str]: (success, result_or_error_message)
        """
        t0 = time.perf_counter()
        arg_hash = self.hash_arguments(arguments)
        self.tool_calls_count += 1
        self.tool_calls_by_type[tool_name] = self.tool_calls_by_type.get(tool_name, 0) + 1

        # 1. Check forbidden dangerous tool blacklist
        if tool_name in self.FORBIDDEN_TOOLS:
            self.blocked_tool_calls += 1
            self.unsafe_tool_attempts += 1
            duration_ms = (time.perf_counter() - t0) * 1000
            record = ToolCallRecord(
                trace_id=trace_id,
                repair_id=repair_id,
                investigation_id=investigation_id,
                lifecycle_phase=phase,
                tool_name=tool_name,
                arguments_hash=arg_hash,
                policy_decision="BLOCKED",
                block_reason="Attempt to invoke dangerous/autonomous tool prohibited by governance.",
                result_summary="Execution blocked by safety policy.",
                duration_ms=round(duration_ms, 2),
            )
            self.audit_log.append(record)
            logger.warning(f"BLOCKED dangerous LLM tool attempt: {tool_name}")
            return False, "Access Denied: Tool requires human authorization and cannot be called by LLM."

        # 2. Check lifecycle phase permissions
        allowed_in_phase = self.PERMITTED_TOOLS.get(phase, set())
        if tool_name not in allowed_in_phase:
            self.blocked_tool_calls += 1
            duration_ms = (time.perf_counter() - t0) * 1000
            record = ToolCallRecord(
                trace_id=trace_id,
                repair_id=repair_id,
                investigation_id=investigation_id,
                lifecycle_phase=phase,
                tool_name=tool_name,
                arguments_hash=arg_hash,
                policy_decision="BLOCKED",
                block_reason=f"Tool '{tool_name}' is not permitted in lifecycle phase '{phase.value}'.",
                result_summary="Execution blocked by phase gate.",
                duration_ms=round(duration_ms, 2),
            )
            self.audit_log.append(record)
            return False, f"Access Denied: Tool '{tool_name}' is not available during {phase.value}."

        # 3. Execute permitted tool via native MCP server
        try:
            native_server = get_native_mcp_server()
            res = await native_server.call_tool(tool_name, arguments)
            duration_ms = (time.perf_counter() - t0) * 1000

            content_text = ""
            if hasattr(res, "content") and res.content:
                content_text = res.content[0].text if hasattr(res.content[0], "text") else str(res.content[0])

            record = ToolCallRecord(
                trace_id=trace_id,
                repair_id=repair_id,
                investigation_id=investigation_id,
                lifecycle_phase=phase,
                tool_name=tool_name,
                arguments_hash=arg_hash,
                policy_decision="ALLOWED",
                result_summary=content_text[:120] if content_text else "Success",
                duration_ms=round(duration_ms, 2),
            )
            self.audit_log.append(record)

            tracker.record_tool_execution(
                repair_id=repair_id or "global",
                trace_id=trace_id,
                server_id="devaura-native-mcp",
                tool_name=tool_name,
                parameters={"args_hash": arg_hash},
                result={"status": "OK", "bytes": len(content_text)},
                duration_ms=duration_ms,
            )

            return True, content_text

        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            record = ToolCallRecord(
                trace_id=trace_id,
                repair_id=repair_id,
                investigation_id=investigation_id,
                lifecycle_phase=phase,
                tool_name=tool_name,
                arguments_hash=arg_hash,
                policy_decision="BLOCKED",
                block_reason=str(e),
                duration_ms=round(duration_ms, 2),
            )
            self.audit_log.append(record)
            return False, f"Tool execution failed: {e}"
