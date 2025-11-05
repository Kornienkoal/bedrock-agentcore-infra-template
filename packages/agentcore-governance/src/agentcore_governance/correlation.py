"""Correlation ID helpers aligning audit events across systems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import uuid


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


def new_correlation_context(*, user: str | None = None, agent: str | None = None, tool: str | None = None) -> CorrelationContext:
    """Create a new correlation context with a generated trace identifier."""
    trace_id = uuid.uuid4().hex
    return CorrelationContext(trace_id=trace_id, user=user, agent=agent, tool=tool)
