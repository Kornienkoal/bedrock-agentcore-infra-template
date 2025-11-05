"""Agent-to-tool authorization mapping utilities."""

from __future__ import annotations

from collections.abc import Iterable


def get_authorized_tools(agent_id: str) -> list[str]:
    """Return the tools currently authorized for an agent."""
    raise NotImplementedError("Authorization lookup not yet implemented")


def set_authorized_tools(agent_id: str, tools: Iterable[str]) -> None:
    """Persist the tools authorized for the given agent."""
    raise NotImplementedError("Authorization update not yet implemented")
