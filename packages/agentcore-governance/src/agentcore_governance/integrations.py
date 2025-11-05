"""Third-party integration allowlist management."""

from __future__ import annotations

from typing import Any


def request_integration(payload: dict[str, Any]) -> str:
    """Record an integration request and return its identifier."""
    raise NotImplementedError("Integration request handler not yet implemented")


def approve_integration(
    integration_id: str, *, approved_targets: list[str], expiry_days: int | None
) -> None:
    """Approve a pending integration request."""
    raise NotImplementedError("Integration approval flow not yet implemented")
