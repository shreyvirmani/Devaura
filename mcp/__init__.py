"""Devaura Model Context Protocol (MCP) Package.

Seamlessly bridges official MCP 2.x SDK with Devaura's architectural
client, native server, registry, policy, and models layers.
"""
import os
import sys

# Extend package __path__ with site-packages mcp so official SDK modules
# (mcp.types, mcp.server.mcpserver, mcp.client.session, etc.) are fully accessible.
for p in sys.path:
    if "site-packages" in p:
        candidate = os.path.join(p, "mcp")
        if os.path.isdir(candidate) and candidate not in __path__:
            __path__.append(candidate)
