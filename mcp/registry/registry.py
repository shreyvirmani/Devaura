import asyncio
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.logger import logger
from database.connection import get_session_maker
from database.models import MCPServer as DBMCPServer, MCPTool as DBMCPTool, ToolExecution as DBToolExecution
from mcp.client.mcp_client import DevauraMCPClient
from mcp.models import (
    MCPApprovalRequiredError,
    MCPError,
    MCPPolicyDeniedError,
    MCPServerInfo,
    MCPServerUnavailableError,
    MCPToolInfo,
    MCPToolNotFoundError,
    PolicyAction,
    RiskLevel,
    ServerTrustLevel,
    ToolCallResult,
    TransportType,
)
from mcp.policy.policy_engine import policy_engine
from mcp.server.devaura_server import get_native_mcp_server


class MCPServerRegistry:
    """Manages MCP server registrations, connection lifecycles, capability discovery,
    runtime clients pool, and policy-governed tool execution.
    """

    def __init__(self):
        # Runtime cache: server_id -> MCPServerInfo
        self._servers: Dict[str, MCPServerInfo] = {}
        # Runtime clients pool: server_id -> DevauraMCPClient
        self._clients: Dict[str, DevauraMCPClient] = {}
        self._initialized = False

    async def initialize_defaults(self, session: Optional[AsyncSession] = None) -> None:
        """Register and connect default Devaura Native MCP Server."""
        if self._initialized:
            return

        # 1. Native Devaura Server
        native_id = "srv_devaura_native"
        native_server_info = MCPServerInfo(
            id=native_id,
            name="Devaura Native",
            transport=TransportType.NATIVE,
            endpoint="internal://devaura-native",
            status="disconnected",
            trust_level=ServerTrustLevel.TRUSTED,
            enabled=True,
            configuration={"builtin": True},
        )
        self._servers[native_id] = native_server_info
        native_instance = get_native_mcp_server()
        client = DevauraMCPClient(
            native_server_info,
            native_server_instance=native_instance,
        )
        self._clients[native_id] = client

        # Auto-connect native server
        try:
            await client.connect()
            await client.list_tools()
            await client.list_prompts()
        except Exception as e:
            logger.warning(f"Failed to auto-connect native server: {e}")

        # 2. Persist in DB if session is available
        if session:
            existing = await session.scalar(select(DBMCPServer).where(DBMCPServer.id == native_id))
            if not existing:
                db_server = DBMCPServer(
                    id=native_id,
                    name=native_server_info.name,
                    transport=native_server_info.transport.value,
                    endpoint=native_server_info.endpoint,
                    status=native_server_info.status,
                    configuration=native_server_info.configuration,
                )
                session.add(db_server)
                await session.flush()

        self._initialized = True

    async def register_server(
        self,
        name: str,
        transport: str = "stdio",
        endpoint: str = "",
        configuration: Optional[Dict[str, Any]] = None,
        trust_level: ServerTrustLevel = ServerTrustLevel.TRUSTED,
        session: Optional[AsyncSession] = None,
    ) -> MCPServerInfo:
        """Register a new MCP server in the registry and database."""
        # Check duplicate by name
        for s in self._servers.values():
            if s.name.lower() == name.lower():
                raise MCPError(f"MCP server with name '{name}' is already registered.")

        try:
            parsed_transport = TransportType(transport.lower())
        except ValueError:
            parsed_transport = TransportType.STDIO

        server_id = f"srv_{name.lower().replace(' ', '_').replace('-', '_')}"
        info = MCPServerInfo(
            id=server_id,
            name=name,
            transport=parsed_transport,
            endpoint=endpoint,
            status="registered",
            trust_level=trust_level,
            enabled=True,
            configuration=configuration or {},
        )

        self._servers[server_id] = info
        self._clients[server_id] = DevauraMCPClient(info)

        # Persist to database if session provided
        if session:
            db_server = DBMCPServer(
                id=server_id,
                name=name,
                transport=parsed_transport.value,
                endpoint=endpoint,
                status=info.status,
                configuration=info.configuration,
            )
            session.add(db_server)
            await session.flush()

        logger.info(f"Registered MCP server '{name}' (ID: {server_id})", extra={"component": "mcp_registry", "server": name})
        return info

    async def get_server(self, server_id: str) -> Optional[MCPServerInfo]:
        """Retrieve server runtime info."""
        await self._ensure_initialized()
        return self._servers.get(server_id)

    async def list_servers(self) -> List[MCPServerInfo]:
        """List all registered servers and their capabilities."""
        await self._ensure_initialized()
        return list(self._servers.values())

    async def connect_server(self, server_id: str, session: Optional[AsyncSession] = None) -> MCPServerInfo:
        """Establish connection with server and discover capabilities."""
        await self._ensure_initialized()
        client = self._clients.get(server_id)
        if not client:
            raise MCPServerUnavailableError(f"MCP server '{server_id}' not found in registry.")

        await client.connect()
        await self.refresh_capabilities(server_id, session=session)
        return client.server_info

    async def disconnect_server(self, server_id: str, session: Optional[AsyncSession] = None) -> MCPServerInfo:
        """Disconnect server cleanly."""
        await self._ensure_initialized()
        client = self._clients.get(server_id)
        if not client:
            raise MCPServerUnavailableError(f"MCP server '{server_id}' not found.")

        await client.disconnect()
        if session:
            db_server = await session.scalar(select(DBMCPServer).where(DBMCPServer.id == server_id))
            if db_server:
                db_server.status = "disconnected"
                await session.flush()

        return client.server_info

    async def refresh_capabilities(self, server_id: str, session: Optional[AsyncSession] = None) -> MCPServerInfo:
        """Discover tools, resources, and prompts from server, syncing persistent tool metadata."""
        client = self._clients.get(server_id)
        if not client:
            raise MCPServerUnavailableError(f"MCP server '{server_id}' not found.")

        tools = await client.list_tools()
        await client.list_resources()
        await client.list_prompts()

        # Sync tool definitions to DB if session provided
        if session:
            for tool in tools:
                existing_tool = await session.scalar(
                    select(DBMCPTool).where(
                        DBMCPTool.server_id == server_id,
                        DBMCPTool.name == tool.name,
                    )
                )
                if not existing_tool:
                    db_tool = DBMCPTool(
                        server_id=server_id,
                        name=tool.name,
                        description=tool.description,
                        input_schema=tool.input_schema,
                        risk_level=tool.risk_level.value,
                        enabled=tool.enabled,
                    )
                    session.add(db_tool)
            await session.flush()

        return client.server_info

    async def remove_server(self, server_id: str, session: Optional[AsyncSession] = None) -> None:
        """Disconnect and remove server from registry and database."""
        client = self._clients.pop(server_id, None)
        if client:
            await client.disconnect()
        self._servers.pop(server_id, None)

        if session:
            db_server = await session.scalar(select(DBMCPServer).where(DBMCPServer.id == server_id))
            if db_server:
                await session.delete(db_server)
                await session.flush()

    async def execute_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        investigation_id: Optional[str] = None,
        approval_token: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> ToolCallResult:
        """Execute a tool through the ToolPolicyEngine and audit logging pipeline."""
        await self._ensure_initialized()
        client = self._clients.get(server_id)
        if not client:
            raise MCPServerUnavailableError(f"Server '{server_id}' is not connected or registered.")

        # Locate tool metadata
        tool_info = client._cached_tools.get(tool_name)
        risk = tool_info.risk_level if tool_info else RiskLevel.SAFE
        is_enabled = tool_info.enabled if tool_info else True

        # Policy Engine Evaluation
        decision = policy_engine.authorize(
            tool_name=tool_name,
            risk_level=risk,
            server_trust=client.server_info.trust_level,
            tool_enabled=is_enabled,
            user_id=user_id,
            arguments=arguments,
            approval_token=approval_token,
        )

        # Handle Policy Decision
        if decision.decision == PolicyAction.DENY:
            logger.warning(
                f"Policy Blocked: {tool_name} on {server_id}: {decision.reason}",
                extra={"component": "mcp_registry", "server": server_id, "tool": tool_name, "decision": "DENY"},
            )
            # Record audit trace if session provided
            await self._audit_execution(
                server_id=server_id,
                tool_name=tool_name,
                arguments=arguments or {},
                output={"error": decision.reason, "policy": "DENY"},
                status="blocked_by_policy",
                latency_ms=0.0,
                investigation_id=investigation_id,
                session=session,
            )
            raise MCPPolicyDeniedError(decision.reason)

        if decision.decision == PolicyAction.REQUIRE_APPROVAL:
            # Register the pending approval token in the policy store
            if decision.approval_token:
                policy_engine.register_approval(
                    token=decision.approval_token,
                    tool_name=tool_name,
                    user_id=user_id or "anonymous",
                    metadata={"server_id": server_id, "arguments": arguments},
                )
            logger.info(
                f"Policy Approval Required: {tool_name} on {server_id}. Token: {decision.approval_token}",
                extra={"component": "mcp_registry", "server": server_id, "tool": tool_name},
            )
            raise MCPApprovalRequiredError(
                message=decision.reason,
                approval_token=decision.approval_token or "",
            )

        # Action is ALLOW: invoke tool
        result = await client.call_tool(tool_name, arguments=arguments)

        # Record audit log
        await self._audit_execution(
            server_id=server_id,
            tool_name=tool_name,
            arguments=arguments or {},
            output={"result": result.content, "is_error": result.is_error},
            status="error" if result.is_error else "success",
            latency_ms=result.latency_ms,
            investigation_id=investigation_id,
            session=session,
        )

        return result

    async def _audit_execution(
        self,
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        output: Dict[str, Any],
        status: str,
        latency_ms: float,
        investigation_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Persist execution audit entry in database."""
        if session:
            try:
                audit = DBToolExecution(
                    investigation_id=investigation_id,
                    server=server_id,
                    tool=tool_name,
                    input_data=arguments,
                    output_data=output,
                    status=status,
                    latency_ms=latency_ms,
                )
                session.add(audit)
                await session.flush()
            except Exception as e:
                logger.warning(f"Failed to record tool execution audit: {e}")

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize_defaults()


# Singleton global registry instance
registry = MCPServerRegistry()
