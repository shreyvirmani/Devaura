"""Devaura MCP Client Subpackage.

Extends __path__ to allow seamless coexistence with official mcp.client SDK modules.
"""
import os
import sys

# Extend subpackage __path__ with site-packages mcp/client
for p in sys.path:
    if "site-packages" in p:
        candidate = os.path.join(p, "mcp", "client")
        if os.path.isdir(candidate) and candidate not in __path__:
            __path__.append(candidate)

from mcp.client.mcp_client import DevauraMCPClient

__all__ = ["DevauraMCPClient"]
