import asyncio
import os
import shlex
import sys
import time
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from apps.api.logger import logger
from mcp.models import (
    MCPAuthError,
    MCPConnectionError,
    MCPError,
    MCPExecutionError,
    MCPInvalidArgumentsError,
    MCPPromptArgument,
    MCPPromptInfo,
    MCPProtocolError,
    MCPResourceInfo,
    MCPServerInfo,
    MCPTimeoutError,
    MCPToolInfo,
    MCPToolNotFoundError,
    RiskLevel,
    ServerTrustLevel,
    ToolCallResult,
    TransportType,
)


class DevauraMCPClient:
    """Production-grade MCP Client connecting to external and native MCP servers
    using the official Model Context Protocol 2.x SDK.
    """

    def __init__(
        self,
        server_info: MCPServerInfo,
        connect_timeout_seconds: float = 15.0,
        tool_timeout_seconds: float = 60.0,
        native_server_instance: Optional[Any] = None,
    ):
        self.server_info = server_info
        self.connect_timeout = connect_timeout_seconds
        self.tool_timeout = tool_timeout_seconds
        self.native_server = native_server_instance
        self._session = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._connected = False
        self._cached_tools: Dict[str, MCPToolInfo] = {}
        self._cached_resources: Dict[str, MCPResourceInfo] = {}
        self._cached_prompts: Dict[str, MCPPromptInfo] = {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Establish connection with the MCP server based on configured transport."""
        if self._connected:
            return

        logger.info(
            f"Connecting to MCP server '{self.server_info.name}' via {self.server_info.transport}",
            extra={"component": "mcp_client", "server": self.server_info.name, "transport": self.server_info.transport},
        )

        try:
            async with asyncio.timeout(self.connect_timeout):
                if self.server_info.transport == TransportType.NATIVE:
                    await self._connect_native()
                elif self.server_info.transport == TransportType.STDIO:
                    await self._connect_stdio()
                elif self.server_info.transport in (TransportType.SSE, TransportType.HTTP):
                    await self._connect_sse()
                else:
                    raise MCPConnectionError(f"Unsupported MCP transport: {self.server_info.transport}")

            self._connected = True
            self.server_info.status = "connected"
            logger.info(
                f"Successfully connected to MCP server '{self.server_info.name}'",
                extra={"component": "mcp_client", "server": self.server_info.name, "status": "connected"},
            )
        except asyncio.TimeoutError as e:
            self._connected = False
            self.server_info.status = "error"
            await self.disconnect()
            raise MCPTimeoutError(
                f"Connection to MCP server '{self.server_info.name}' timed out after {self.connect_timeout}s",
                details={"server": self.server_info.name, "endpoint": self.server_info.endpoint},
            ) from e
        except MCPError:
            self._connected = False
            self.server_info.status = "error"
            await self.disconnect()
            raise
        except Exception as e:
            self._connected = False
            self.server_info.status = "error"
            await self.disconnect()
            raise MCPConnectionError(
                f"Failed to connect to MCP server '{self.server_info.name}': {str(e)}",
                details={"server": self.server_info.name, "error": str(e)},
            ) from e

    async def _connect_native(self) -> None:
        """In-process native server connection."""
        if self.native_server is None:
            # Lazy import Devaura Native MCP Server
            from mcp.server.devaura_server import get_native_mcp_server
            self.native_server = get_native_mcp_server()
        # Native in-process is immediately ready
        self._session = self.native_server

    async def _connect_stdio(self) -> None:
        """STDIO process-based MCP connection using official SDK."""
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        # Parse command and args
        parts = shlex.split(self.server_info.endpoint, posix=(os.name != "nt"))
        if not parts:
            raise MCPConnectionError("Empty command specified for STDIO MCP server endpoint")

        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        env = os.environ.copy()
        if self.server_info.configuration and "env" in self.server_info.configuration:
            env.update(self.server_info.configuration["env"])

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

        exit_stack = AsyncExitStack()
        try:
            read_stream, write_stream = await exit_stack.enter_async_context(stdio_client(server_params))
            session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            self._session = session
            self._exit_stack = exit_stack
        except Exception as e:
            await exit_stack.aclose()
            raise MCPConnectionError(f"STDIO launch failed for '{command}': {str(e)}") from e

    async def _connect_sse(self) -> None:
        """HTTP/SSE based MCP connection using official SDK."""
        from mcp.client.session import ClientSession
        from mcp.client.sse import sse_client

        url = self.server_info.endpoint
        headers = self.server_info.configuration.get("headers", {})

        exit_stack = AsyncExitStack()
        try:
            read_stream, write_stream = await exit_stack.enter_async_context(
                sse_client(url=url, headers=headers, timeout=self.connect_timeout)
            )
            session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            self._session = session
            self._exit_stack = exit_stack
        except Exception as e:
            await exit_stack.aclose()
            raise MCPConnectionError(f"SSE connection failed for '{url}': {str(e)}") from e

    async def disconnect(self) -> None:
        """Disconnect and clean up resources cleanly."""
        self._connected = False
        self.server_info.status = "disconnected"
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.warning(f"Error while closing MCP connection stack: {e}")
            finally:
                self._exit_stack = None
        self._session = None

    async def list_tools(self) -> List[MCPToolInfo]:
        """Discover tools exposed by the connected MCP server."""
        if not self._connected:
            await self.connect()

        try:
            tools_list: List[MCPToolInfo] = []
            if self.server_info.transport == TransportType.NATIVE:
                raw_tools = await self.native_server.list_tools()
                for tool in raw_tools:
                    fn = getattr(tool, "fn", None)
                    risk = getattr(fn, "risk_level", None) if fn else None
                    if not risk:
                        risk = getattr(tool, "risk_level", None)
                    if not risk:
                        risk = self._classify_tool_risk(tool.name)
                    if isinstance(risk, str):
                        try:
                            risk = RiskLevel(risk)
                        except ValueError:
                            risk = RiskLevel.SAFE
                    tool_info = MCPToolInfo(
                        server_id=self.server_info.id,
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.parameters if hasattr(tool, "parameters") else {},
                        risk_level=risk,
                        enabled=True,
                    )
                    tools_list.append(tool_info)
            else:
                sdk_result = await self._session.list_tools()
                for tool in sdk_result.tools:
                    schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}
                    # Derive default risk classification based on name conventions if not annotated
                    risk = self._classify_tool_risk(tool.name)
                    tool_info = MCPToolInfo(
                        server_id=self.server_info.id,
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=schema,
                        risk_level=risk,
                        enabled=True,
                    )
                    tools_list.append(tool_info)

            # Update cache
            self._cached_tools = {t.name: t for t in tools_list}
            self.server_info.tools = tools_list
            return tools_list
        except Exception as e:
            raise MCPProtocolError(f"Failed to list tools from '{self.server_info.name}': {str(e)}") from e

    async def list_resources(self) -> List[MCPResourceInfo]:
        """Discover resources exposed by the connected MCP server."""
        if not self._connected:
            await self.connect()

        try:
            resources_list: List[MCPResourceInfo] = []
            if self.server_info.transport == TransportType.NATIVE:
                raw_resources = await self.native_server.list_resources()
                for res in raw_resources:
                    resources_list.append(
                        MCPResourceInfo(
                            server_id=self.server_info.id,
                            uri=str(res.uri),
                            name=res.name,
                            description=res.description,
                            mime_type=res.mime_type if hasattr(res, "mime_type") else None,
                        )
                    )
            else:
                sdk_result = await self._session.list_resources()
                for res in sdk_result.resources:
                    resources_list.append(
                        MCPResourceInfo(
                            server_id=self.server_info.id,
                            uri=str(res.uri),
                            name=res.name,
                            description=res.description if hasattr(res, "description") else None,
                            mime_type=res.mimeType if hasattr(res, "mimeType") else None,
                        )
                    )
            self._cached_resources = {r.uri: r for r in resources_list}
            self.server_info.resources = resources_list
            return resources_list
        except Exception as e:
            raise MCPProtocolError(f"Failed to list resources from '{self.server_info.name}': {str(e)}") from e

    async def list_prompts(self) -> List[MCPPromptInfo]:
        """Discover standardized prompts exposed by the connected MCP server."""
        if not self._connected:
            await self.connect()

        try:
            prompts_list: List[MCPPromptInfo] = []
            if self.server_info.transport == TransportType.NATIVE:
                raw_prompts = await self.native_server.list_prompts()
                for prompt in raw_prompts:
                    args = []
                    if hasattr(prompt, "arguments") and prompt.arguments:
                        for a in prompt.arguments:
                            args.append(
                                MCPPromptArgument(
                                    name=a.name,
                                    description=getattr(a, "description", None),
                                    required=getattr(a, "required", False),
                                )
                            )
                    prompts_list.append(
                        MCPPromptInfo(
                            server_id=self.server_info.id,
                            name=prompt.name,
                            description=prompt.description,
                            arguments=args,
                        )
                    )
            else:
                sdk_result = await self._session.list_prompts()
                for prompt in sdk_result.prompts:
                    args = []
                    if hasattr(prompt, "arguments") and prompt.arguments:
                        for a in prompt.arguments:
                            args.append(
                                MCPPromptArgument(
                                    name=a.name,
                                    description=getattr(a, "description", None),
                                    required=getattr(a, "required", False),
                                )
                            )
                    prompts_list.append(
                        MCPPromptInfo(
                            server_id=self.server_info.id,
                            name=prompt.name,
                            description=prompt.description if hasattr(prompt, "description") else None,
                            arguments=args,
                        )
                    )
            self._cached_prompts = {p.name: p for p in prompts_list}
            self.server_info.prompts = prompts_list
            return prompts_list
        except Exception as e:
            raise MCPProtocolError(f"Failed to list prompts from '{self.server_info.name}': {str(e)}") from e

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> ToolCallResult:
        """Execute a tool on the connected server with timeout, error handling, and latency measurement."""
        if not self._connected:
            await self.connect()

        arguments = arguments or {}
        start_time = time.time()

        try:
            async with asyncio.timeout(self.tool_timeout):
                if self.server_info.transport == TransportType.NATIVE:
                    result = await self.native_server.call_tool(tool_name, arguments)
                    latency = round((time.time() - start_time) * 1000.0, 2)
                    
                    # Unpack tool result
                    content_str = ""
                    is_err = False
                    if hasattr(result, "is_error"):
                        is_err = bool(result.is_error)
                    if hasattr(result, "content") and result.content:
                        for item in result.content:
                            if hasattr(item, "text"):
                                content_str += item.text
                            else:
                                content_str += str(item)
                    else:
                        content_str = str(result)

                    return ToolCallResult(
                        server=self.server_info.name,
                        tool=tool_name,
                        content=content_str,
                        is_error=is_err,
                        latency_ms=latency,
                        raw_result=result,
                    )
                else:
                    result = await self._session.call_tool(tool_name, arguments=arguments)
                    latency = round((time.time() - start_time) * 1000.0, 2)
                    content_str = ""
                    is_err = bool(getattr(result, "isError", False))

                    if hasattr(result, "content") and result.content:
                        for item in result.content:
                            if hasattr(item, "text"):
                                content_str += item.text
                            else:
                                content_str += str(item)
                    else:
                        content_str = str(result)

                    return ToolCallResult(
                        server=self.server_info.name,
                        tool=tool_name,
                        content=content_str,
                        is_error=is_err,
                        latency_ms=latency,
                        raw_result=result,
                    )
        except asyncio.TimeoutError as e:
            latency = round((time.time() - start_time) * 1000.0, 2)
            raise MCPTimeoutError(
                f"Tool '{tool_name}' execution timed out after {self.tool_timeout}s",
                details={"server": self.server_info.name, "tool": tool_name, "latency_ms": latency},
            ) from e
        except MCPError:
            raise
        except Exception as e:
            latency = round((time.time() - start_time) * 1000.0, 2)
            raise MCPExecutionError(
                f"Error invoking tool '{tool_name}' on server '{self.server_info.name}': {str(e)}",
                details={"server": self.server_info.name, "tool": tool_name, "error": str(e), "latency_ms": latency},
            ) from e

    async def read_resource(self, uri: str) -> str:
        """Read content from an MCP resource."""
        if not self._connected:
            await self.connect()

        try:
            if self.server_info.transport == TransportType.NATIVE:
                result = await self.native_server.read_resource(uri)
                if hasattr(result, "contents") and result.contents:
                    return str(result.contents[0].text if hasattr(result.contents[0], "text") else result.contents[0])
                return str(result)
            else:
                result = await self._session.read_resource(uri)
                if hasattr(result, "contents") and result.contents:
                    return str(result.contents[0].text if hasattr(result.contents[0], "text") else result.contents[0])
                return str(result)
        except Exception as e:
            raise MCPProtocolError(f"Failed to read resource '{uri}': {str(e)}") from e

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Retrieve a standardized prompt from the server."""
        if not self._connected:
            await self.connect()

        try:
            if self.server_info.transport == TransportType.NATIVE:
                return await self.native_server.get_prompt(name, arguments or {})
            else:
                return await self._session.get_prompt(name, arguments=arguments or {})
        except Exception as e:
            raise MCPProtocolError(f"Failed to get prompt '{name}': {str(e)}") from e

    def _classify_tool_risk(self, tool_name: str) -> RiskLevel:
        """Deterministic risk classifier based on tool name semantics."""
        name = tool_name.lower()
        # DANGEROUS operations
        if any(keyword in name for keyword in ["push", "merge", "delete", "deploy", "drop", "destroy", "approve_repair", "apply_approved_patch"]):
            return RiskLevel.DANGEROUS
        # CONTROLLED mutations
        if any(keyword in name for keyword in ["run_", "test", "patch", "apply", "commit", "branch", "execute", "write", "verification"]):
            return RiskLevel.CONTROLLED
        # SAFE read-only operations
        return RiskLevel.SAFE
