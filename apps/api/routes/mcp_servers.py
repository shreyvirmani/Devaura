from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import CurrentUser, get_current_user
from database.connection import get_db_session
from database.models import MCPServer as DBMCPServer, MCPTool as DBMCPTool
from mcp.models import (
    MCPApprovalRequiredError,
    MCPError,
    MCPPolicyDeniedError,
    MCPServerInfo,
    MCPServerUnavailableError,
    MCPToolInfo,
    PolicyAction,
    RiskLevel,
    ServerTrustLevel,
    ToolCallResult,
    TransportType,
)
from mcp.policy.policy_engine import policy_engine
from mcp.registry.registry import registry

router = APIRouter(prefix="/mcp", tags=["MCP Management"])


# Schemas
class MCPToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    server_id: str
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str
    enabled: bool = True


class MCPResourceResponse(BaseModel):
    server_id: str
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPPromptResponse(BaseModel):
    server_id: str
    name: str
    description: Optional[str] = None
    arguments: List[Dict[str, Any]] = Field(default_factory=list)


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    transport: str
    endpoint: str
    status: str
    trust_level: str = "TRUSTED"
    enabled: bool = True
    configuration: Dict[str, Any] = Field(default_factory=dict)
    tools: List[MCPToolResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MCPServerCreate(BaseModel):
    name: str = Field(..., examples=["github-mcp"])
    transport: str = Field(default="stdio", examples=["stdio", "sse", "native"])
    endpoint: str = Field(..., examples=["npx -y @modelcontextprotocol/server-github"])
    trust_level: str = Field(default="TRUSTED", examples=["TRUSTED", "UNTRUSTED", "DISABLED"])
    configuration: Dict[str, Any] = Field(default_factory=dict)


class ToolExecuteRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)
    investigation_id: Optional[str] = None
    approval_token: Optional[str] = None


class ToolExecuteResponse(BaseModel):
    server: str
    tool: str
    content: Any
    is_error: bool = False
    latency_ms: float = 0.0
    status: str = "success"
    requires_approval: bool = False
    approval_token: Optional[str] = None
    reason: Optional[str] = None


class ApprovalRequest(BaseModel):
    token: str
    tool_name: str
    approved: bool = True


@router.get("/servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[MCPServerResponse]:
    """List all registered MCP servers with runtime state and capability metadata."""
    await registry.initialize_defaults(session=session)
    runtime_servers = await registry.list_servers()

    responses: List[MCPServerResponse] = []
    for s in runtime_servers:
        responses.append(
            MCPServerResponse(
                id=s.id,
                name=s.name,
                transport=s.transport.value,
                endpoint=s.endpoint,
                status=s.status,
                trust_level=s.trust_level.value,
                enabled=s.enabled,
                configuration=s.configuration,
                tools=[
                    MCPToolResponse(
                        server_id=t.server_id,
                        name=t.name,
                        description=t.description,
                        input_schema=t.input_schema,
                        risk_level=t.risk_level.value,
                        enabled=t.enabled,
                    )
                    for t in s.tools
                ],
            )
        )
    return responses


@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(
    payload: MCPServerCreate,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> MCPServerResponse:
    """Register a new MCP server endpoint."""
    try:
        trust = ServerTrustLevel(payload.trust_level.upper())
    except ValueError:
        trust = ServerTrustLevel.TRUSTED

    try:
        info = await registry.register_server(
            name=payload.name,
            transport=payload.transport,
            endpoint=payload.endpoint,
            configuration=payload.configuration,
            trust_level=trust,
            session=session,
        )
        return MCPServerResponse(
            id=info.id,
            name=info.name,
            transport=info.transport.value,
            endpoint=info.endpoint,
            status=info.status,
            trust_level=info.trust_level.value,
            enabled=info.enabled,
            configuration=info.configuration,
            tools=[],
        )
    except MCPError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/servers/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> MCPServerResponse:
    """Retrieve details for a single MCP server."""
    info = await registry.get_server(server_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"MCP Server '{server_id}' not found.")

    return MCPServerResponse(
        id=info.id,
        name=info.name,
        transport=info.transport.value,
        endpoint=info.endpoint,
        status=info.status,
        trust_level=info.trust_level.value,
        enabled=info.enabled,
        configuration=info.configuration,
        tools=[
            MCPToolResponse(
                server_id=t.server_id,
                name=t.name,
                description=t.description,
                input_schema=t.input_schema,
                risk_level=t.risk_level.value,
                enabled=t.enabled,
            )
            for t in info.tools
        ],
    )


@router.delete("/servers/{server_id}", status_code=status.HTTP_200_OK)
async def remove_mcp_server(
    server_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, str]:
    """Unregister and disconnect an MCP server."""
    await registry.remove_server(server_id, session=session)
    return {"message": f"Server '{server_id}' successfully removed."}


@router.post("/servers/{server_id}/connect", response_model=MCPServerResponse)
async def connect_mcp_server(
    server_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> MCPServerResponse:
    """Establish connection and discover server capabilities."""
    try:
        info = await registry.connect_server(server_id, session=session)
        return MCPServerResponse(
            id=info.id,
            name=info.name,
            transport=info.transport.value,
            endpoint=info.endpoint,
            status=info.status,
            trust_level=info.trust_level.value,
            enabled=info.enabled,
            configuration=info.configuration,
            tools=[
                MCPToolResponse(
                    server_id=t.server_id,
                    name=t.name,
                    description=t.description,
                    input_schema=t.input_schema,
                    risk_level=t.risk_level.value,
                    enabled=t.enabled,
                )
                for t in info.tools
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("/servers/{server_id}/disconnect", response_model=MCPServerResponse)
async def disconnect_mcp_server(
    server_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> MCPServerResponse:
    """Disconnect an MCP server cleanly."""
    try:
        info = await registry.disconnect_server(server_id, session=session)
        return MCPServerResponse(
            id=info.id,
            name=info.name,
            transport=info.transport.value,
            endpoint=info.endpoint,
            status=info.status,
            trust_level=info.trust_level.value,
            enabled=info.enabled,
            configuration=info.configuration,
            tools=[],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/refresh", response_model=MCPServerResponse)
async def refresh_mcp_server_capabilities(
    server_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> MCPServerResponse:
    """Refresh tools, resources, and prompts from server."""
    try:
        info = await registry.refresh_capabilities(server_id, session=session)
        return MCPServerResponse(
            id=info.id,
            name=info.name,
            transport=info.transport.value,
            endpoint=info.endpoint,
            status=info.status,
            trust_level=info.trust_level.value,
            enabled=info.enabled,
            configuration=info.configuration,
            tools=[
                MCPToolResponse(
                    server_id=t.server_id,
                    name=t.name,
                    description=t.description,
                    input_schema=t.input_schema,
                    risk_level=t.risk_level.value,
                    enabled=t.enabled,
                )
                for t in info.tools
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}/tools", response_model=List[MCPToolResponse])
async def list_mcp_tools(
    server_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[MCPToolResponse]:
    """List tools discovered from a specific MCP server."""
    info = await registry.get_server(server_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")

    return [
        MCPToolResponse(
            server_id=t.server_id,
            name=t.name,
            description=t.description,
            input_schema=t.input_schema,
            risk_level=t.risk_level.value,
            enabled=t.enabled,
        )
        for t in info.tools
    ]


@router.get("/servers/{server_id}/resources", response_model=List[MCPResourceResponse])
async def list_mcp_resources(
    server_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> List[MCPResourceResponse]:
    """List resources exposed by server."""
    info = await registry.get_server(server_id)
    if not info:
        raise HTTPException(status_code=404, detail="Server not found.")

    return [
        MCPResourceResponse(
            server_id=r.server_id,
            uri=r.uri,
            name=r.name,
            description=r.description,
            mime_type=r.mime_type,
        )
        for r in info.resources
    ]


@router.get("/servers/{server_id}/prompts", response_model=List[MCPPromptResponse])
async def list_mcp_prompts(
    server_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> List[MCPPromptResponse]:
    """List prompts exposed by server."""
    info = await registry.get_server(server_id)
    if not info:
        raise HTTPException(status_code=404, detail="Server not found.")

    return [
        MCPPromptResponse(
            server_id=p.server_id,
            name=p.name,
            description=p.description,
            arguments=[{"name": a.name, "description": a.description, "required": a.required} for a in p.arguments],
        )
        for p in info.prompts
    ]


@router.post("/servers/{server_id}/tools/{tool_name}/execute", response_model=ToolExecuteResponse)
async def execute_mcp_tool(
    server_id: str,
    tool_name: str,
    payload: ToolExecuteRequest,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> ToolExecuteResponse:
    """Execute an MCP tool subject to policy engine validation, approval verification, and audit logging."""
    try:
        result = await registry.execute_tool(
            server_id=server_id,
            tool_name=tool_name,
            arguments=payload.arguments,
            user_id=user.id,
            investigation_id=payload.investigation_id,
            approval_token=payload.approval_token,
            session=session,
        )
        return ToolExecuteResponse(
            server=result.server,
            tool=result.tool,
            content=result.content,
            is_error=result.is_error,
            latency_ms=result.latency_ms,
            status="error" if result.is_error else "success",
        )
    except MCPApprovalRequiredError as e:
        return ToolExecuteResponse(
            server=server_id,
            tool=tool_name,
            content="",
            is_error=False,
            status="approval_required",
            requires_approval=True,
            approval_token=e.approval_token,
            reason=e.message,
        )
    except MCPPolicyDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tool execution blocked by policy: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}",
        )


@router.post("/policy/approve")
async def approve_tool_execution(
    payload: ApprovalRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Human Approval Gate: Grant approval for a pending DANGEROUS tool execution token."""
    if not payload.approved:
        policy_engine.consume_approval(payload.token)
        return {"token": payload.token, "status": "rejected", "message": "Approval was denied by user."}

    policy_engine.register_approval(
        token=payload.token,
        tool_name=payload.tool_name,
        user_id=user.id,
    )
    return {
        "token": payload.token,
        "tool_name": payload.tool_name,
        "status": "approved",
        "approved_by": user.email,
        "message": f"Tool '{payload.tool_name}' approved. Submit execution with approval_token.",
    }
