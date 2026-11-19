import os
import re
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from apps.api.logger import logger
from mcp.models import (
    MCPPolicyDeniedError,
    MCPApprovalRequiredError,
    MCPToolInfo,
    PolicyAction,
    PolicyDecision,
    RiskLevel,
    ServerTrustLevel,
)

# Standard Safe Command Executables Allowlist
ALLOWED_COMMANDS: Set[str] = {
    "pytest",
    "python",
    "python3",
    "ruff",
    "flake8",
    "mypy",
    "pyright",
    "npm",
    "npx",
    "git",
}

# Dangerous shell pattern blacklist
DISALLOWED_SHELL_PATTERNS = [
    re.compile(r"[;&|`$]"),          # Command chaining & substitution
    re.compile(r"[<>]"),              # Redirections
    re.compile(r"\b(rm\s+-rf|del\s+/f|mkfs|dd|curl|wget|bash|sh|cmd|powershell)\b", re.IGNORECASE),
    re.compile(r"\b(id_rsa|\.env|shadow|passwd)\b", re.IGNORECASE),
]


class PathSecurityViolation(MCPPolicyDeniedError):
    """Raised when a tool attempts to access files outside the authorized workspace."""
    pass


class CommandSecurityViolation(MCPPolicyDeniedError):
    """Raised when a tool attempts to run an unapproved or dangerous command."""
    pass


class ToolPolicyEngine:
    """Production policy and permission engine governing all MCP tool invocations.
    
    Enforces risk classifications, server trust levels, command allowlists,
    path traversal guards, and human approval gates.
    """

    def __init__(self):
        # Store for active human approvals: token -> approval metadata
        self._approved_tokens: Dict[str, Dict[str, Any]] = {}

    def authorize(
        self,
        tool_name: str,
        risk_level: RiskLevel,
        server_trust: ServerTrustLevel = ServerTrustLevel.TRUSTED,
        tool_enabled: bool = True,
        user_id: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        approval_token: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluate and authorize or deny an MCP tool execution request."""
        arguments = arguments or {}
        audit_id = f"pol_{secrets.token_hex(8)}"

        # 1. Server trust check
        if server_trust == ServerTrustLevel.DISABLED:
            logger.warning(
                f"Policy DENY: Server is DISABLED for tool '{tool_name}'",
                extra={"component": "policy_engine", "audit_id": audit_id, "decision": "DENY"},
            )
            return PolicyDecision(
                decision=PolicyAction.DENY,
                risk_level=risk_level,
                reason="Server is currently disabled by administrator policy.",
                audit_id=audit_id,
            )

        # 2. Tool enabled check
        if not tool_enabled:
            logger.warning(
                f"Policy DENY: Tool '{tool_name}' is disabled",
                extra={"component": "policy_engine", "audit_id": audit_id, "decision": "DENY"},
            )
            return PolicyDecision(
                decision=PolicyAction.DENY,
                risk_level=risk_level,
                reason=f"Tool '{tool_name}' is explicitly disabled on this server.",
                audit_id=audit_id,
            )

        # 3. Untrusted server restrictions
        if server_trust == ServerTrustLevel.UNTRUSTED and risk_level != RiskLevel.SAFE:
            logger.warning(
                f"Policy DENY: Untrusted server requested non-SAFE tool '{tool_name}'",
                extra={"component": "policy_engine", "audit_id": audit_id, "decision": "DENY"},
            )
            return PolicyDecision(
                decision=PolicyAction.DENY,
                risk_level=risk_level,
                reason="Untrusted MCP servers may only execute SAFE read-only tools.",
                audit_id=audit_id,
            )

        # 4. SAFE operations are automatically permitted
        if risk_level == RiskLevel.SAFE:
            return PolicyDecision(
                decision=PolicyAction.ALLOW,
                risk_level=risk_level,
                reason="SAFE read-only tool approved automatically by policy.",
                audit_id=audit_id,
            )

        # 5. CONTROLLED operations (run_tests, apply_patch, etc.)
        if risk_level == RiskLevel.CONTROLLED:
            # If arguments contain command execution, validate command allowlist
            if "command" in arguments:
                try:
                    self.validate_command(arguments["command"])
                except CommandSecurityViolation as e:
                    return PolicyDecision(
                        decision=PolicyAction.DENY,
                        risk_level=risk_level,
                        reason=str(e),
                        audit_id=audit_id,
                    )

            # If arguments contain file paths, validate path boundaries
            if "workspace" in arguments and "path" in arguments:
                try:
                    self.validate_workspace_path(arguments["workspace"], arguments["path"])
                except PathSecurityViolation as e:
                    return PolicyDecision(
                        decision=PolicyAction.DENY,
                        risk_level=risk_level,
                        reason=str(e),
                        audit_id=audit_id,
                    )

            return PolicyDecision(
                decision=PolicyAction.ALLOW,
                risk_level=risk_level,
                reason="CONTROLLED sandboxed operation validated and permitted.",
                audit_id=audit_id,
            )

        # 6. DANGEROUS operations (push_branch, create_pull_request, deploy)
        if risk_level == RiskLevel.DANGEROUS:
            if approval_token and self.is_approved(approval_token, tool_name):
                # Consume approval token (one-time use for safety)
                self.consume_approval(approval_token)
                logger.info(
                    f"Policy ALLOW: DANGEROUS tool '{tool_name}' authorized with valid approval token",
                    extra={"component": "policy_engine", "audit_id": audit_id, "tool": tool_name},
                )
                return PolicyDecision(
                    decision=PolicyAction.ALLOW,
                    risk_level=risk_level,
                    reason="DANGEROUS operation explicitly approved by authorized human operator.",
                    requires_approval=False,
                    approval_token=approval_token,
                    audit_id=audit_id,
                )

            # Require human approval gate
            new_token = f"appr_{secrets.token_urlsafe(16)}"
            logger.info(
                f"Policy REQUIRE_APPROVAL: DANGEROUS tool '{tool_name}' requires human approval",
                extra={"component": "policy_engine", "audit_id": audit_id, "token": new_token},
            )
            return PolicyDecision(
                decision=PolicyAction.REQUIRE_APPROVAL,
                risk_level=risk_level,
                reason=f"Tool '{tool_name}' is classified as DANGEROUS and requires explicit human approval before execution.",
                requires_approval=True,
                approval_token=new_token,
                audit_id=audit_id,
            )

        return PolicyDecision(
            decision=PolicyAction.DENY,
            risk_level=risk_level,
            reason="Unrecognized risk level.",
            audit_id=audit_id,
        )

    # Path Traversal Guard
    def validate_workspace_path(self, workspace_root: str | Path, requested_path: str) -> Path:
        """Ensure requested path resolves strictly within the authorized workspace boundary."""
        base = Path(workspace_root).resolve()
        target = (base / requested_path).resolve()

        # Reject path traversal / directory escapes
        if not target.is_relative_to(base):
            raise PathSecurityViolation(
                f"Path traversal detected: '{requested_path}' resolves outside workspace '{base}'"
            )

        # Reject null bytes or dangerous characters
        if "\0" in str(requested_path):
            raise PathSecurityViolation("Null byte injection detected in file path.")

        return target

    # Command Policy & Allowlist
    def validate_command(self, command_str: str) -> List[str]:
        """Validate command string against strict allowlists and regex patterns.
        
        Disallows arbitrary shell execution and ensures commands are safe.
        """
        if not command_str or not command_str.strip():
            raise CommandSecurityViolation("Empty command is not permitted.")

        # Check for disallowed shell patterns
        for pattern in DISALLOWED_SHELL_PATTERNS:
            if pattern.search(command_str):
                raise CommandSecurityViolation(
                    f"Disallowed command pattern detected in '{command_str}'. Shell operators, redirects, and dangerous commands are strictly forbidden."
                )

        # Parse command tokens safely
        tokens = command_str.strip().split()
        if not tokens:
            raise CommandSecurityViolation("Invalid command tokens.")

        executable = Path(tokens[0]).stem.lower()
        if executable not in ALLOWED_COMMANDS:
            raise CommandSecurityViolation(
                f"Executable '{executable}' is not in the allowed command policy allowlist: {sorted(list(ALLOWED_COMMANDS))}"
            )

        return tokens

    # Human Approval Store
    def register_approval(self, token: str, tool_name: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register a valid human approval for a pending dangerous operation."""
        self._approved_tokens[token] = {
            "token": token,
            "tool_name": tool_name,
            "user_id": user_id,
            "metadata": metadata or {},
        }

    def is_approved(self, token: str, tool_name: str) -> bool:
        """Check if an approval token is valid for the specified tool."""
        record = self._approved_tokens.get(token)
        if not record:
            return False
        return record["tool_name"] == tool_name

    def consume_approval(self, token: str) -> None:
        """Consume an approval token so it cannot be reused."""
        self._approved_tokens.pop(token, None)


# Default global policy engine instance
policy_engine = ToolPolicyEngine()
