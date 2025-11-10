"""Correlation ID helpers aligning audit events across systems."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CorrelationContext:
    trace_id: str
    user: str | None = None
    agent: str | None = None
    tool: str | None = None

    def to_headers(self) -> Mapping[str, str]:
        """Render correlation metadata as outbound headers."""
        parts: list[str] = [f"trace={self.trace_id}"]
        if self.user:
            parts.append(f"user={self.user}")
        if self.agent:
            parts.append(f"agent={self.agent}")
        if self.tool:
            parts.append(f"tool={self.tool}")
        return {"X-Correlation-Id": ";".join(parts)}

    def __enter__(self) -> str:
        """Support use of the context in `with` blocks returning the trace id."""

        return self.trace_id

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:  # noqa: D401 - std context protocol
        """No-op exit hook for context manager compatibility."""

        return False


def new_correlation_context(
    *, user: str | None = None, agent: str | None = None, tool: str | None = None
) -> CorrelationContext:
    """Create a correlation context object with a generated trace identifier."""

    trace_id = uuid.uuid4().hex
    return CorrelationContext(trace_id=trace_id, user=user, agent=agent, tool=tool)


@contextmanager
def correlation_scope(
    *, user: str | None = None, agent: str | None = None, tool: str | None = None
):
    """Context manager wrapper that yields a :class:`CorrelationContext`."""

    ctx = new_correlation_context(user=user, agent=agent, tool=tool)
    yield ctx
