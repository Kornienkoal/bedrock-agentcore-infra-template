"""API handlers for governance endpoints."""

from __future__ import annotations

from . import (
    analyzer_handlers,
    authorization_handlers,
    catalog_handlers,
    decision_handlers,
    evidence_handlers,
    integration_handlers,
    metrics,
    revocation_handlers,
)

__all__ = [
    "analyzer_handlers",
    "authorization_handlers",
    "catalog_handlers",
    "decision_handlers",
    "evidence_handlers",
    "integration_handlers",
    "metrics",
    "revocation_handlers",
]
