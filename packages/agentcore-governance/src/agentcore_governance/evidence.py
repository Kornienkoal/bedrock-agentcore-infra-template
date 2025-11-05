"""Evidence pack generation utilities."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from agentcore_governance import integrity

logger = logging.getLogger(__name__)


def construct_audit_event(
    event_type: str,
    correlation_id: str,
    principal_chain: list[str],
    outcome: str,
    latency_ms: int = 0,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a standardized audit event record.

    Args:
        event_type: Type of event (agent_invocation, tool_invocation, etc.)
        correlation_id: Correlation identifier for tracing
        principal_chain: List of principals involved in the operation
        outcome: Result of the operation (success, failure, denied, etc.)
        latency_ms: Operation latency in milliseconds
        additional_fields: Optional extra fields to include

    Returns:
        Audit event dictionary with integrity hash
    """
    event_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "principal_chain": principal_chain,
        "outcome": outcome,
        "latency_ms": latency_ms,
    }

    if additional_fields:
        event.update(additional_fields)

    # Compute integrity hash over core fields
    hash_fields = [
        event_id,
        event_type,
        timestamp,
        correlation_id,
        "|".join(principal_chain),
        outcome,
        str(latency_ms),
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    return event


def build_evidence_pack(parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate an evidence pack artifact description.

    Args:
        parameters: Optional parameters (hours_back for log range, etc.)

    Returns:
        Evidence pack metadata with catalog snapshot and audit event summary
    """
    params = parameters or {}
    hours_back = params.get("hours_back", 24)

    pack_id = uuid.uuid4().hex
    generated_at = datetime.now(UTC)

    # Fetch catalog snapshot (simplified - would call catalog.fetch_principal_catalog)
    try:
        from agentcore_governance import catalog

        principals = catalog.fetch_principal_catalog()
        principal_count = len(principals)
    except Exception as e:
        logger.warning(f"Could not fetch catalog for evidence pack: {e}")
        principal_count = 0

    # Query CloudWatch Logs for audit events (simplified)
    missing_events = 0
    try:
        missing_events = _detect_missing_events(hours_back)
    except Exception as e:
        logger.warning(f"Could not detect missing events: {e}")

    # Compute conformance score (would aggregate from analyzer)
    conformance_score = _compute_conformance_score(principals) if principal_count > 0 else 0.0

    pack = {
        "id": pack_id,
        "generated_at": generated_at.isoformat(),
        "principal_snapshot_count": principal_count,
        "audit_event_range_hours": hours_back,
        "conformance_score": conformance_score,
        "missing_events": missing_events,
    }

    logger.info(f"Generated evidence pack {pack_id} with {principal_count} principals")
    return pack


def _detect_missing_events(hours_back: int) -> int:
    """Detect missing or incomplete audit events in recent logs.

    Args:
        hours_back: Hours of history to scan

    Returns:
        Count of detected missing events
    """
    # Simplified implementation - would query CloudWatch Logs Insights
    # for correlation IDs with incomplete chains
    _ = hours_back  # TODO: Implement CloudWatch Logs query
    return 0


def _compute_conformance_score(principals: list[dict[str, Any]]) -> float:
    """Compute average conformance score across principals.

    Args:
        principals: List of principal records

    Returns:
        Average least_privilege_score
    """
    if not principals:
        return 0.0

    scores = [p.get("least_privilege_score", 0.0) for p in principals]
    return sum(scores) / len(scores) if scores else 0.0
