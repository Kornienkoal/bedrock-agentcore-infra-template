"""REST API handlers for policy decision endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# In-memory decision registry for demonstration
# In production, this would query CloudWatch Logs or a persistent store
_decision_registry: list[dict[str, Any]] = []


def list_decisions(
    subject_id: str | None = None,
    effect: str | None = None,
    hours_back: int = 24,
    limit: int = 100,
    resource_pattern: str | None = None,
    action_pattern: str | None = None,
    aggregate_by: str | None = None,
) -> dict[str, Any]:
    """Handle GET /decisions request with enhanced filtering and aggregation (T079).

    Retrieves policy decisions with optional filtering by subject and effect.
    Includes correlation tracing for audit trail reconstruction.

    Args:
        subject_id: Optional subject identifier filter
        effect: Optional decision effect filter (allow or deny)
        hours_back: Time window for query (default 24 hours)
        limit: Maximum number of results to return
        resource_pattern: Optional resource pattern filter (substring match)
        action_pattern: Optional action pattern filter (substring match)
        aggregate_by: Optional aggregation field (subject_id, effect, resource)

    Returns:
        Response with decisions array and query metadata (with optional aggregations)
    """
    try:
        # Calculate time threshold
        cutoff = datetime.now(UTC) - timedelta(hours=hours_back)

        # Filter decisions from registry
        decisions = _decision_registry.copy()

        # Apply subject_id filter
        if subject_id:
            decisions = [d for d in decisions if d.get("subject_id") == subject_id]

        # Apply effect filter
        if effect:
            effect_lower = effect.lower()
            if effect_lower not in ("allow", "deny"):
                return {
                    "error": "Invalid effect value. Must be 'allow' or 'deny'",
                    "status": 400,
                }
            decisions = [d for d in decisions if d.get("effect") == effect_lower]

        # Apply resource pattern filter
        if resource_pattern:
            decisions = [
                d for d in decisions if resource_pattern.lower() in d.get("resource", "").lower()
            ]

        # Apply action pattern filter
        if action_pattern:
            decisions = [
                d for d in decisions if action_pattern.lower() in d.get("action", "").lower()
            ]

        # Apply time filter
        decisions = [
            d
            for d in decisions
            if datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")) >= cutoff
        ]

        # Compute aggregations if requested
        aggregations: dict[str, Any] = {}
        if aggregate_by and aggregate_by in ("subject_id", "effect", "resource", "action"):
            agg_map: dict[str, int] = {}
            for decision in decisions:
                key = str(decision.get(aggregate_by, "unknown"))
                agg_map[key] = agg_map.get(key, 0) + 1
            aggregations[f"by_{aggregate_by}"] = dict(sorted(agg_map.items()))

        # Apply limit to result set
        limited_decisions = decisions[:limit]

        # Sort by timestamp descending (most recent first)
        limited_decisions.sort(key=lambda x: x["timestamp"], reverse=True)

        response: dict[str, Any] = {
            "decisions": limited_decisions,
            "count": len(limited_decisions),
            "total_matching": len(decisions),
            "filters": {
                "subject_id": subject_id,
                "effect": effect,
                "hours_back": hours_back,
                "resource_pattern": resource_pattern,
                "action_pattern": action_pattern,
            },
            "status": 200,
        }

        if aggregations:
            response["aggregations"] = aggregations

        return response

    except Exception as e:
        logger.error(f"Error listing decisions: {e}", exc_info=True)
        return {
            "error": f"Failed to list decisions: {e!s}",
            "status": 500,
        }


def record_decision(
    subject_type: str,
    subject_id: str,
    action: str,
    resource: str,
    effect: str,
    policy_reference: str,
    correlation_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Record a policy decision for audit trail.

    Args:
        subject_type: Type of subject (user, agent, integration)
        subject_id: Subject identifier
        action: Action being attempted
        resource: Resource being accessed
        effect: Decision effect (allow or deny)
        policy_reference: Reference to policy that made decision
        correlation_id: Correlation identifier for tracing
        reason: Optional explanation for decision

    Returns:
        Recorded decision with generated ID
    """
    import uuid

    decision_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).isoformat()

    decision = {
        "id": decision_id,
        "timestamp": timestamp,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "action": action,
        "resource": resource,
        "effect": effect.lower(),
        "policy_reference": policy_reference,
        "correlation_id": correlation_id,
    }

    if reason:
        decision["reason"] = reason

    # Store in registry
    _decision_registry.append(decision)

    # Limit registry size (keep last 10000 decisions)
    if len(_decision_registry) > 10000:
        _decision_registry[:] = _decision_registry[-10000:]

    logger.info(f"Recorded policy decision {decision_id}: {effect} for {subject_id} on {resource}")

    return decision


def get_decisions_for_correlation(correlation_id: str) -> list[dict[str, Any]]:
    """Retrieve all decisions associated with a correlation ID.

    Args:
        correlation_id: Correlation identifier to search for

    Returns:
        List of decisions with matching correlation ID
    """
    decisions = [d for d in _decision_registry if d.get("correlation_id") == correlation_id]
    decisions.sort(key=lambda x: x["timestamp"])
    return decisions
