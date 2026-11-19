from datetime import datetime
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.auth import CurrentUser, get_current_user
from database.connection import get_db_session
from database.models import MCPServer, MCPTool, RiskLevel

router = APIRouter(prefix="/mcp", tags=["MCP Management"])


class MCPToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    server_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: str
    enabled: bool


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    transport: str
    endpoint: str
    status: str
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    tools: List[MCPToolResponse] = []


class MCPServerCreate(BaseModel):
    name: str = Field(..., examples=["github-mcp"])
    transport: str = Field(default="stdio", examples=["stdio"])
    endpoint: str = Field(..., examples=["npx -y @modelcontextprotocol/server-github"])
    configuration: dict[str, Any] = Field(default_factory=dict)


@router.get("/servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[MCPServerResponse]:
    """List all registered MCP servers and their current connectivity status."""
    result = await session.execute(select(MCPServer).order_by(MCPServer.name.asc()))
    return list(result.scalars().all())


@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(
    payload: MCPServerCreate,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> MCPServerResponse:
    """Register a new MCP server endpoint."""
    existing = await session.execute(select(MCPServer).where(MCPServer.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"MCP Server '{payload.name}' already registered.",
        )

    server = MCPServer(
        name=payload.name,
        transport=payload.transport,
        endpoint=payload.endpoint,
        status="registered",
        configuration=payload.configuration,
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


@router.get("/servers/{server_id}/tools", response_model=List[MCPToolResponse])
async def list_mcp_tools(
    server_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[MCPToolResponse]:
    """List tools discovered from a specific MCP server."""
    result = await session.execute(
        select(MCPTool).where(MCPTool.server_id == server_id).order_by(MCPTool.name.asc())
    )
    return list(result.scalars().all())
