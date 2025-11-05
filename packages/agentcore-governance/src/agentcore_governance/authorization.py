"""Agent-to-tool authorization mapping utilities."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# In-memory authorization store: agent_id -> list of tool_ids
_authorization_store: dict[str, list[str]] = {}

# History for differential reporting: agent_id -> list of change records
_authorization_history: dict[str, list[dict[str, Any]]] = {}


def get_authorized_tools(agent_id: str) -> list[str]:
    """Return the tools currently authorized for an agent.

    Args:
        agent_id: Agent identifier

    Returns:
        List of tool IDs authorized for this agent
    """
    return _authorization_store.get(agent_id, []).copy()


def set_authorized_tools(
    agent_id: str,
    tools: Iterable[str],
    reason: str | None = None,
) -> dict[str, Any]:
    """Update the tools authorized for an agent and record change history.

    Args:
        agent_id: Agent identifier
        tools: List of tool IDs to authorize
        reason: Optional justification for the change

    Returns:
        Differential report with added/removed/unchanged tools
    """
    tool_list = list(tools)
    previous_tools = _authorization_store.get(agent_id, [])

    # Compute differential
    previous_set = set(previous_tools)
    new_set = set(tool_list)

    added = sorted(new_set - previous_set)
    removed = sorted(previous_set - new_set)
    unchanged = sorted(previous_set & new_set)

    # Update store
    _authorization_store[agent_id] = tool_list

    # Record change in history
    change_record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_id": agent_id,
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "reason": reason,
        "total_before": len(previous_tools),
        "total_after": len(tool_list),
    }

    if agent_id not in _authorization_history:
        _authorization_history[agent_id] = []
    _authorization_history[agent_id].append(change_record)

    logger.info(
        f"Authorization updated for {agent_id}: "
        f"+{len(added)} -{len(removed)} ={len(unchanged)}"
    )

    return change_record


def generate_differential_report(agent_id: str) -> dict[str, Any]:
    """Generate a differential report of authorization changes for an agent.

    Args:
        agent_id: Agent identifier

    Returns:
        Report with current state and change history
    """
    current_tools = get_authorized_tools(agent_id)
    history = _authorization_history.get(agent_id, [])

    return {
        "agent_id": agent_id,
        "current_tools": current_tools,
        "total_changes": len(history),
        "change_history": history,
    }


def check_tool_authorized(agent_id: str, tool_id: str) -> bool:
    """Check if a specific tool is authorized for an agent.

    Args:
        agent_id: Agent identifier
        tool_id: Tool identifier

    Returns:
        True if tool is authorized, False otherwise
    """
    authorized_tools = get_authorized_tools(agent_id)
    return tool_id in authorized_tools


def refresh_authorization_store(mappings: dict[str, list[str]]) -> None:
    """Refresh the entire authorization store (e.g., from external source).

    Args:
        mappings: Dictionary of agent_id -> list of tool_ids
    """
    global _authorization_store
    _authorization_store = {agent_id: tools.copy() for agent_id, tools in mappings.items()}
    logger.info(f"Authorization store refreshed: {len(_authorization_store)} agents")


def clear_authorization_store() -> None:
    """Clear the authorization store and history (for testing)."""
    global _authorization_store, _authorization_history
    _authorization_store = {}
    _authorization_history = {}
