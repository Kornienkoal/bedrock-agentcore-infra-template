"""Gateway helpers that integrate with MCP/Strands.

This module provides thin wrappers that depend on optional tool/runtime
dependencies (Strands + MCP HTTP client). The low-level control-plane
helpers and tool filtering logic live in ``agentcore_common.gateway`` to
avoid importing optional packages in minimal contexts.
"""

from __future__ import annotations

import logging
from typing import Any

from agentcore_common.gateway import filter_tools_by_allowed
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient


def create_mcp_client(
    gateway_url: str,
    authorization_header: str,
) -> MCPClient:
    """Create an MCPClient context manager for a Gateway URL and Authorization header.

    Usage:
        >>> with create_mcp_client(url, header) as client:
        ...     tools = client.list_tools_sync()
    """

    return MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url, headers={"Authorization": authorization_header}
        )
    )


def load_gateway_tools(
    gateway_url: str,
    authorization_header: str,
    gateway_cfg: Any,
    logger: logging.Logger | None = None,
) -> list[Any]:
    """List Gateway tools via MCP and apply allowed-tools filtering.

    Args:
        gateway_url: Full Gateway MCP base URL
        authorization_header: Value of the Authorization header (e.g., "Bearer <token>")
        gateway_cfg: The ``gateway`` section from agent config for filtering
        logger: Optional logger

    Returns:
        A list of Tool objects (as returned by MCP client), filtered as configured.
    """

    with create_mcp_client(gateway_url, authorization_header) as client:
        tools = client.list_tools_sync()
        # Explicit type annotation required by mypy to avoid no-any-return error
        filtered: list[Any] = filter_tools_by_allowed(tools, gateway_cfg, logger)
        return filtered
