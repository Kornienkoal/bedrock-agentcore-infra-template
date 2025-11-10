"""API handlers for emergency revocation management."""

from __future__ import annotations

import logging
from typing import Any

from agentcore_governance import correlation, evidence, revocation

logger = logging.getLogger(__name__)


def handle_revocation_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle POST /revocations request.

    Args:
        payload: Request body with subjectType, subjectId, scope, reason

    Returns:
        Response with revocation_id and status

    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Generate correlation ID for tracking
    response: dict[str, Any] | None = None
    with correlation.new_correlation_context() as corr_id:
        try:
            # Validate payload
            required_fields = ["subjectType", "subjectId", "scope"]
            for field in required_fields:
                if field not in payload:
                    raise ValueError(f"Missing required field: {field}")

            # Create revocation request
            revocation_id = revocation.create_revocation_request(payload)

            # Emit audit event
            event = evidence.construct_revocation_request_event(
                revocation_id=revocation_id,
                subject_type=payload["subjectType"],
                subject_id=payload["subjectId"],
                scope=payload["scope"],
                reason=payload.get("reason", ""),
                initiated_by=payload.get("initiatedBy", "unknown"),
                correlation_id=corr_id,
            )
            logger.info(f"Revocation request audit event: {event['id']}")

            response = {
                "revocation_id": revocation_id,
                "status": "pending",
                "message": "Revocation request recorded and pending propagation",
                "correlation_id": corr_id,
            }

        except ValueError as e:
            logger.error(f"Revocation request validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Revocation request failed: {e}")
            raise

    if response is None:
        raise RuntimeError("Revocation request response not generated")
    return response


def handle_revocation_get(revocation_id: str) -> dict[str, Any]:
    """Handle GET /revocations/{revocationId} request.

    Args:
        revocation_id: Revocation identifier

    Returns:
        Revocation details with status and metrics

    Raises:
        ValueError: If revocation not found
    """
    try:
        revocation_record = revocation.get_revocation_status(revocation_id)

        # Add computed fields
        response = dict(revocation_record)

        # Add SLA status if complete
        if revocation_record["status"] == "complete":
            latency_ms = revocation_record["propagation_latency_ms"]
            sla_target_ms = revocation_record["sla_target_seconds"] * 1000
            response["sla_met"] = latency_ms <= sla_target_ms
            response["sla_status"] = "met" if response["sla_met"] else "breached"

        return response

    except ValueError as e:
        logger.error(f"Revocation get failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Revocation get failed: {e}")
        raise


def handle_revocation_propagate(revocation_id: str) -> dict[str, Any]:
    """Handle revocation propagation completion (internal use).

    Args:
        revocation_id: Revocation identifier

    Returns:
        Updated revocation with SLA metrics

    Raises:
        ValueError: If revocation not found or already propagated
    """
    # Generate correlation ID for tracking
    response: dict[str, Any] | None = None
    with correlation.new_correlation_context() as corr_id:
        try:
            # Mark as propagated
            updated_revocation = revocation.mark_revocation_propagated(revocation_id)

            # Emit SLA metric
            latency_ms = updated_revocation["propagation_latency_ms"]
            sla_met = updated_revocation["sla_met"]
            sla_target_ms = updated_revocation["sla_target_seconds"] * 1000

            metric = revocation.emit_sla_metric()

            # Emit audit event
            event = evidence.construct_revocation_propagated_event(
                revocation_id=revocation_id,
                latency_ms=latency_ms,
                sla_met=sla_met,
                correlation_id=corr_id,
            )
            logger.info(f"Revocation propagated audit event: {event['id']}")

            response = {
                "revocation_id": revocation_id,
                "status": "complete",
                "propagation_latency_ms": latency_ms,
                "sla_met": sla_met,
                "sla_target_ms": sla_target_ms,
                "metric": metric,
                "correlation_id": corr_id,
            }

        except ValueError as e:
            logger.error(f"Revocation propagation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Revocation propagation failed: {e}")
            raise

    if response is None:
        raise RuntimeError("Revocation propagation response not generated")
    return response


def handle_revocations_list(
    status: str | None = None, subject_type: str | None = None
) -> dict[str, Any]:
    """Handle GET /revocations request.

    Args:
        status: Optional status filter
        subject_type: Optional subject type filter

    Returns:
        List of revocations with metrics
    """
    revocations = revocation.list_revocations(status=status, subject_type=subject_type)

    # Compute overall SLA metrics
    sla_metrics = revocation.compute_sla_metrics()

    return {
        "revocations": revocations,
        "count": len(revocations),
        "filters": {"status": status, "subject_type": subject_type},
        "sla_metrics": sla_metrics,
    }


def check_subject_revoked(
    subject_type: str, subject_id: str, attempted_action: str | None = None
) -> bool:
    """Check if a subject has an active revocation.

    Args:
        subject_type: Type of subject (user, integration, tool, agent, principal)
        subject_id: Subject identifier
        attempted_action: Optional action being attempted

    Returns:
        True if subject is revoked, False otherwise
    """
    is_revoked = revocation.is_subject_revoked(subject_type, subject_id)

    if is_revoked and attempted_action:
        # Emit denial audit event
        with correlation.new_correlation_context() as corr_id:
            event = evidence.construct_revocation_access_denied_event(
                subject_type=subject_type,
                subject_id=subject_id,
                attempted_action=attempted_action,
                correlation_id=corr_id,
            )
            logger.warning(f"Revocation access denied audit event: {event['id']}")

    return is_revoked
