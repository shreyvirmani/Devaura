from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CONTROLLED = "CONTROLLED"
    DANGEROUS = "DANGEROUS"


class ServerTrustLevel(str, Enum):
    TRUSTED = "TRUSTED"
    UNTRUSTED = "UNTRUSTED"
    DISABLED = "DISABLED"


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    NATIVE = "native"


class PolicyAction(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class MCPToolInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_id: str
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.SAFE
    enabled: bool = True


class MCPResourceInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_id: str
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPPromptArgument(BaseModel):
    name: str
    description: Optional[str] = None
    required: bool = False


class MCPPromptInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_id: str
    name: str
    description: Optional[str] = None
    arguments: List[MCPPromptArgument] = Field(default_factory=list)


class MCPServerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    transport: TransportType = TransportType.STDIO
    endpoint: str
    status: str = "disconnected"  # connected, disconnected, error, registered
    trust_level: ServerTrustLevel = ServerTrustLevel.TRUSTED
    enabled: bool = True
    configuration: Dict[str, Any] = Field(default_factory=dict)
    tools: List[MCPToolInfo] = Field(default_factory=list)
    resources: List[MCPResourceInfo] = Field(default_factory=list)
    prompts: List[MCPPromptInfo] = Field(default_factory=list)
    connected_at: Optional[datetime] = None


class PolicyDecision(BaseModel):
    decision: PolicyAction
    risk_level: RiskLevel
    reason: str
    requires_approval: bool = False
    approval_token: Optional[str] = None
    audit_id: Optional[str] = None


class ToolCallResult(BaseModel):
    server: str
    tool: str
    content: Any
    is_error: bool = False
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    raw_result: Optional[Any] = None


# Structured Exceptions
class MCPError(Exception):
    """Base exception for all MCP-related errors."""
    def __init__(self, message: str, code: str = "MCP_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class MCPConnectionError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_CONNECTION_ERROR", details=details)


class MCPAuthError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_AUTH_ERROR", details=details)


class MCPTimeoutError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_TIMEOUT", details=details)


class MCPToolNotFoundError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_TOOL_NOT_FOUND", details=details)


class MCPInvalidArgumentsError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_INVALID_ARGUMENTS", details=details)


class MCPProtocolError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_PROTOCOL_ERROR", details=details)


class MCPPolicyDeniedError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_POLICY_DENIED", details=details)


class MCPApprovalRequiredError(MCPError):
    def __init__(self, message: str, approval_token: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["approval_token"] = approval_token
        super().__init__(message, code="MCP_APPROVAL_REQUIRED", details=details)
        self.approval_token = approval_token


class MCPServerUnavailableError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_SERVER_UNAVAILABLE", details=details)


class MCPExecutionError(MCPError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MCP_EXECUTION_ERROR", details=details)
