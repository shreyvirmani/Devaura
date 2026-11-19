"""Devaura MCP Server Subpackage.

Extends __path__ to allow seamless coexistence with official mcp.server SDK modules.
"""
import os
import sys

# Extend subpackage __path__ with site-packages mcp/server
for p in sys.path:
    if "site-packages" in p:
        candidate = os.path.join(p, "mcp", "server")
        if os.path.isdir(candidate) and candidate not in __path__:
            __path__.append(candidate)

from mcp.server.devaura_server import (
    get_native_mcp_server,
    create_devaura_native_server,
)

__all__ = [
    "get_native_mcp_server",
    "create_devaura_native_server",
]
