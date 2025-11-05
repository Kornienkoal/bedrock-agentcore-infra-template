"""Emergency revocation workflows and propagation tracking."""

from __future__ import annotations

from typing import Any


def create_revocation_request(payload: dict[str, Any]) -> str:
    """Initiate a revocation request and return its identifier."""
    raise NotImplementedError("Revocation creation not yet implemented")


def get_revocation_status(revocation_id: str) -> dict[str, Any]:
    """Retrieve the current status for a revocation."""
    raise NotImplementedError("Revocation status lookup not yet implemented")
