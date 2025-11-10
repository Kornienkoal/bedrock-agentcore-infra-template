"""Evidence pack generation utilities."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from agentcore_governance import integrity

logger = logging.getLogger(__name__)

# In-memory event store for testing (in production, query CloudWatch Logs)
_event_store: list[dict[str, Any]] = []


def construct_audit_event(
    event_type: str,
    correlation_id: str,
    principal_chain: list[str] | None = None,
    outcome: str = "success",
    latency_ms: int = 0,
    additional_fields: dict[str, Any] | None = None,
    # Alternative signature for simpler test cases
    principal_id: str | None = None,
    action: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a standardized audit event record.

    Args:
        event_type: Type of event (agent_invocation, tool_invocation, etc.)
        correlation_id: Correlation identifier for tracing
        principal_chain: List of principals involved (or use principal_id)
        outcome: Result of the operation (success, failure, denied, etc.)
        latency_ms: Operation latency in milliseconds
        additional_fields: Optional extra fields to include
        principal_id: Single principal (alternative to principal_chain)
        action: Action performed (stored in additional_fields)
        metadata: Metadata (stored in additional_fields)

    Returns:
        Audit event dictionary with integrity hash
    """
    event_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).isoformat()

    # Handle principal_id alternative signature
    if principal_chain is None:
        principal_chain = [principal_id] if principal_id else []

    # Merge metadata and additional_fields
    fields = additional_fields.copy() if additional_fields else {}
    if metadata:
        fields.update(metadata)
    if action and "action" not in fields:
        fields["action"] = action

    event = {
        "id": event_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "principal_chain": principal_chain,
        "outcome": outcome,
        "latency_ms": latency_ms,
    }

    # Add principal_id to top level for test compatibility
    if principal_id:
        event["principal_id"] = principal_id

    # Add fields
    if fields:
        event.update(fields)

    # Compute integrity hash

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


def detect_missing_events(
    events: list[dict[str, Any]],
    expected_sequence: list[str] | None = None,
) -> dict[str, Any]:
    """Detect missing or incomplete events in an audit trail.

    Analyzes correlation chains to identify gaps based on expected
    event sequences (e.g., request → decision → outcome).

    Args:
        events: List of audit events to analyze
        expected_sequence: Optional list of expected event types in order

    Returns:
        Analysis with missing_events count, incomplete_chains, and alerts
    """
    if not events:
        return {
            "missing_events": 0,
            "incomplete_chains": [],
            "alerts": [],
        }

    # Group events by correlation ID
    chains: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        corr_id = event.get("correlation_id", "unknown")
        if corr_id not in chains:
            chains[corr_id] = []
        chains[corr_id].append(event)

    # Define default expected sequences for common workflows
    default_sequences = {
        "authorization": ["authorization_decision"],
        "integration": ["integration_request", "integration_approval"],
        "revocation": ["revocation_request", "revocation_propagated"],
    }

    incomplete_chains = []
    alerts = []
    missing_count = 0

    for corr_id, chain_events in chains.items():
        event_types = [e.get("event_type") for e in chain_events]

        # Determine expected sequence based on first event type
        if expected_sequence:
            expected = expected_sequence
        else:
            # Auto-detect expected sequence
            first_type = event_types[0] if event_types else ""
            expected = None
            for _workflow, seq in default_sequences.items():
                if any(t in str(first_type) for t in seq):
                    expected = seq
                    break

        # Check for missing events
        if expected:
            missing = [et for et in expected if et not in event_types]
            if missing:
                missing_count += len(missing)
                incomplete_chains.append(
                    {
                        "correlation_id": corr_id,
                        "present_events": event_types,
                        "missing_events": missing,
                    }
                )
                alerts.append(f"Incomplete chain {corr_id}: missing {', '.join(missing)}")

        # Check for duplicate events (potential replay or logging error)
        seen = set()
        for et in event_types:
            if et in seen:
                alerts.append(f"Duplicate event type {et} in chain {corr_id}")
            seen.add(et)

        # Check for out-of-order timestamps
        timestamps = [e.get("timestamp") for e in chain_events]
        if timestamps != sorted(t for t in timestamps if t is not None):
            alerts.append(f"Out-of-order timestamps in chain {corr_id}")

    return {
        "missing_events": missing_count,
        "incomplete_chains": incomplete_chains,
        "total_chains": len(chains),
        "alerts": alerts,
    }


def reconstruct_correlation_chain(
    correlation_id: str,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconstruct complete event trace from correlation ID.

    Builds end-to-end audit trail by collecting all events with
    matching correlation_id and organizing them chronologically.

    Args:
        correlation_id: Correlation identifier to trace
        events: Optional pre-filtered event list; if None, queries all sources

    Returns:
        Reconstruction with ordered events, summary, and integrity status
    """
    # If events not provided, would query CloudWatch Logs, decision registry, etc.
    if events is None:
        events = _query_events_by_correlation(correlation_id)

    # Filter to matching correlation ID
    chain_events = [e for e in events if e.get("correlation_id") == correlation_id]

    # Sort by timestamp
    chain_events.sort(key=lambda x: x.get("timestamp", ""))

    # Extract event types and timestamps
    event_types = [e.get("event_type") for e in chain_events]
    timestamps = [e.get("timestamp") for e in chain_events]

    # Verify integrity hashes
    integrity_failures = []
    for event in chain_events:
        if "integrity_hash" in event and not event["integrity_hash"]:
            # Would recompute hash and compare
            integrity_failures.append(event.get("id"))

    # Compute chain latency (first to last event)
    latency_ms = 0
    if len(timestamps) >= 2 and timestamps[0] and timestamps[-1]:
        try:
            start = datetime.fromisoformat(str(timestamps[0]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(timestamps[-1]).replace("Z", "+00:00"))
            latency_ms = int((end - start).total_seconds() * 1000)
        except Exception as e:
            logger.warning(f"Could not compute chain latency: {e}")

    # Detect missing events in this chain
    missing_analysis = detect_missing_events(chain_events)

    return {
        "correlation_id": correlation_id,
        "event_count": len(chain_events),
        "events": chain_events,
        "event_types": event_types,
        "timestamps": timestamps,
        "latency_ms": latency_ms,
        "integrity_failures": integrity_failures,
        "missing_events": missing_analysis["missing_events"],
        "alerts": missing_analysis["alerts"],
        "complete": missing_analysis["missing_events"] == 0,
    }


def _query_events_by_correlation(correlation_id: str) -> list[dict[str, Any]]:
    """Query all event sources for events matching correlation ID.

    Args:
        correlation_id: Correlation identifier to search for

    Returns:
        List of matching events from all sources
    """
    events = []

    # Query in-memory event store (for testing)
    for event in _event_store:
        if event.get("correlation_id") == correlation_id:
            events.append(event)

    # Query decision registry
    try:
        from agentcore_governance.api import decision_handlers

        decisions = decision_handlers.get_decisions_for_correlation(correlation_id)
        # Convert decisions to event format
        for decision in decisions:
            events.append(
                {
                    "id": decision["id"],
                    "event_type": "policy_decision",
                    "timestamp": decision["timestamp"],
                    "correlation_id": decision["correlation_id"],
                    "subject_id": decision["subject_id"],
                    "effect": decision["effect"],
                    "resource": decision["resource"],
                }
            )
    except Exception as e:
        logger.warning(f"Could not query decision registry: {e}")

    # Would also query CloudWatch Logs, other registries
    # TODO: Implement CloudWatch Logs Insights query

    return events


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


def construct_authorization_decision_event(
    agent_id: str,
    tool_id: str,
    effect: str,
    reason: str,
    correlation_id: str | None = None,
    classification: str | None = None,
) -> dict[str, Any]:
    """Construct an authorization decision audit event.

    Args:
        agent_id: Agent attempting to use the tool
        tool_id: Tool being accessed
        effect: Decision effect ('allow' or 'deny')
        reason: Explanation for the decision
        correlation_id: Optional correlation ID for tracing
        classification: Optional tool classification level

    Returns:
        Audit event dictionary with authorization decision details
    """
    event_id = str(uuid.uuid4())
    correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": "authorization_decision",
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "agent_id": agent_id,
        "tool_id": tool_id,
        "effect": effect,
        "reason": reason,
        "classification": classification,
    }

    # Compute integrity hash
    hash_fields = [
        event_id,
        timestamp,
        agent_id,
        tool_id,
        effect,
        reason or "",
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    return event


def construct_integration_request_event(
    integration_id: str,
    name: str,
    justification: str,
    requested_targets: list[str],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Construct an integration request audit event.

    Args:
        integration_id: Integration identifier
        name: Integration name
        justification: Request justification
        requested_targets: List of requested target endpoints
        correlation_id: Optional correlation ID for tracing

    Returns:
        Audit event dictionary with integration request details
    """
    event_id = str(uuid.uuid4())
    correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": "integration_request",
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "integration_id": integration_id,
        "integration_name": name,
        "justification": justification,
        "requested_targets": requested_targets,
        "target_count": len(requested_targets),
    }

    # Compute integrity hash
    hash_fields = [
        event_id,
        timestamp,
        integration_id,
        name,
        justification,
        "|".join(sorted(requested_targets)),
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    logger.info(f"Integration request event: {integration_id} ({name})")
    return event


def construct_integration_approval_event(
    integration_id: str,
    approved_by: str,
    approved_targets: list[str],
    expiry_days: int | None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Construct an integration approval audit event.

    Args:
        integration_id: Integration identifier
        approved_by: Identity of the approver
        approved_targets: List of approved target endpoints
        expiry_days: Optional expiry duration in days
        correlation_id: Optional correlation ID for tracing

    Returns:
        Audit event dictionary with integration approval details
    """
    event_id = str(uuid.uuid4())
    correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": "integration_approval",
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "integration_id": integration_id,
        "approved_by": approved_by,
        "approved_targets": approved_targets,
        "target_count": len(approved_targets),
        "expiry_days": expiry_days,
    }

    # Compute integrity hash
    hash_fields = [
        event_id,
        timestamp,
        integration_id,
        approved_by,
        "|".join(sorted(approved_targets)),
        str(expiry_days or "none"),
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    logger.info(f"Integration approval event: {integration_id} by {approved_by}")
    return event


def construct_integration_denial_event(
    integration_id: str,
    target: str,
    reason: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Construct an integration access denial audit event.

    Args:
        integration_id: Integration identifier
        target: Target endpoint that was denied
        reason: Denial reason
        correlation_id: Optional correlation ID for tracing

    Returns:
        Audit event dictionary with integration denial details
    """
    event_id = str(uuid.uuid4())
    correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": "integration_access_denied",
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "integration_id": integration_id,
        "target": target,
        "reason": reason,
    }

    # Compute integrity hash
    hash_fields = [
        event_id,
        timestamp,
        integration_id,
        target,
        reason,
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    logger.warning(f"Integration access denied: {integration_id} -> {target}")
    return event


def construct_revocation_request_event(
    revocation_id: str,
    subject_type: str,
    subject_id: str,
    scope: str,
    reason: str,
    initiated_by: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Construct a revocation request audit event.

    Args:
        revocation_id: Revocation identifier
        subject_type: Type of subject being revoked
        subject_id: Subject identifier
        scope: Revocation scope
        reason: Revocation reason
        initiated_by: Who initiated the revocation
        correlation_id: Optional correlation ID for tracing

    Returns:
        Audit event dictionary with revocation request details
    """
    event_id = str(uuid.uuid4())
    correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": "revocation_request",
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "revocation_id": revocation_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "scope": scope,
        "reason": reason,
        "initiated_by": initiated_by,
    }

    # Compute integrity hash
    hash_fields = [
        event_id,
        timestamp,
        revocation_id,
        subject_type,
        subject_id,
        scope,
        reason,
        initiated_by,
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    logger.info(f"Revocation request event: {revocation_id} ({subject_type}/{subject_id})")
    return event


def construct_revocation_propagated_event(
    revocation_id: str,
    latency_ms: int,
    sla_met: bool,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Construct a revocation propagation complete audit event.

    Args:
        revocation_id: Revocation identifier
        latency_ms: Propagation latency in milliseconds
        sla_met: Whether SLA was met
        correlation_id: Optional correlation ID for tracing

    Returns:
        Audit event dictionary with revocation propagation details
    """
    event_id = str(uuid.uuid4())
    correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": "revocation_propagated",
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "revocation_id": revocation_id,
        "latency_ms": latency_ms,
        "sla_met": sla_met,
    }

    # Compute integrity hash
    hash_fields = [
        event_id,
        timestamp,
        revocation_id,
        str(latency_ms),
        str(sla_met),
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    logger.info(
        f"Revocation propagated event: {revocation_id} latency={latency_ms}ms sla_met={sla_met}"
    )
    return event


def construct_revocation_access_denied_event(
    subject_type: str,
    subject_id: str,
    attempted_action: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Construct a revocation access denial audit event.

    Args:
        subject_type: Type of subject that was denied
        subject_id: Subject identifier
        attempted_action: Action that was attempted
        correlation_id: Optional correlation ID for tracing

    Returns:
        Audit event dictionary with revocation denial details
    """
    event_id = str(uuid.uuid4())
    correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    event = {
        "id": event_id,
        "event_type": "revocation_access_denied",
        "timestamp": timestamp,
        "correlation_id": correlation_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "attempted_action": attempted_action,
        "reason": "Subject has active revocation",
    }

    # Compute integrity hash
    hash_fields = [
        event_id,
        timestamp,
        subject_type,
        subject_id,
        attempted_action,
    ]
    event["integrity_hash"] = integrity.compute_integrity_hash(hash_fields)

    logger.warning(f"Revocation access denied: {subject_type}/{subject_id} -> {attempted_action}")
    return event
