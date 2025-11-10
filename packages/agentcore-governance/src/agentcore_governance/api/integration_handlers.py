"""API handlers for third-party integration management."""

from __future__ import annotations

import logging
from typing import Any

from agentcore_governance import correlation, evidence, integrations

logger = logging.getLogger(__name__)


def handle_integration_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle POST /integrations request.

    Args:
        payload: Request body with name, justification, requestedTargets

    Returns:
        Response with integration_id and status

    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Generate correlation ID for tracking
    response: dict[str, Any] | None = None
    with correlation.new_correlation_context() as corr_id:
        try:
            # Validate payload
            required_fields = ["name", "justification", "requestedTargets"]
            for field in required_fields:
                if field not in payload:
                    raise ValueError(f"Missing required field: {field}")

            if not isinstance(payload["requestedTargets"], list):
                raise ValueError("requestedTargets must be a list")

            if not payload["requestedTargets"]:
                raise ValueError("requestedTargets cannot be empty")

            # Create integration request
            integration_id = integrations.request_integration(payload)

            # Emit audit event
            event = evidence.construct_integration_request_event(
                integration_id=integration_id,
                name=payload["name"],
                justification=payload["justification"],
                requested_targets=payload["requestedTargets"],
                correlation_id=corr_id,
            )
            logger.info(f"Integration request audit event: {event['id']}")

            response = {
                "integration_id": integration_id,
                "status": "pending",
                "message": "Integration request recorded",
                "correlation_id": corr_id,
            }

        except ValueError as e:
            logger.error(f"Integration request validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Integration request failed: {e}")
            raise

    if response is None:
        raise RuntimeError("Integration request response not generated")
    return response


def handle_integration_approval(
    integration_id: str,
    payload: dict[str, Any],
    approved_by: str,
) -> dict[str, Any]:
    """Handle POST /integrations/{integrationId}/approve request.

    Args:
        integration_id: Integration identifier
        payload: Request body with approvedTargets and optional expiryDays
        approved_by: Identity of the approver (from auth context)

    Returns:
        Response with integration details

    Raises:
        ValueError: If integration not found or invalid
    """
    # Generate correlation ID for tracking
    response: dict[str, Any] | None = None
    with correlation.new_correlation_context() as corr_id:
        try:
            # Validate payload
            if "approvedTargets" not in payload:
                raise ValueError("Missing required field: approvedTargets")

            if not isinstance(payload["approvedTargets"], list):
                raise ValueError("approvedTargets must be a list")

            approved_targets = payload["approvedTargets"]
            expiry_days = payload.get("expiryDays")

            if expiry_days is not None and (not isinstance(expiry_days, int) or expiry_days <= 0):
                raise ValueError("expiryDays must be a positive integer")

            # Check integration exists
            integration = integrations.get_integration(integration_id)
            if not integration:
                raise ValueError(f"Integration not found: {integration_id}")

            # Approve integration
            integrations.approve_integration(
                integration_id=integration_id,
                approved_targets=approved_targets,
                expiry_days=expiry_days,
                approved_by=approved_by,
            )

            # Emit audit event
            event = evidence.construct_integration_approval_event(
                integration_id=integration_id,
                approved_by=approved_by,
                approved_targets=approved_targets,
                expiry_days=expiry_days,
                correlation_id=corr_id,
            )
            logger.info(f"Integration approval audit event: {event['id']}")

            # Retrieve updated integration
            updated_integration = integrations.get_integration(integration_id)

            response = {
                "integration_id": integration_id,
                "status": "active",
                "approved_targets": approved_targets,
                "approved_by": approved_by,
                "expires_at": updated_integration.get("expires_at")
                if updated_integration
                else None,
                "correlation_id": corr_id,
            }

        except ValueError as e:
            logger.error(f"Integration approval validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Integration approval failed: {e}")
            raise

    if response is None:
        raise RuntimeError("Integration approval response not generated")
    return response


def handle_integration_get(integration_id: str) -> dict[str, Any]:
    """Handle GET /integrations/{integrationId} request.

    Args:
        integration_id: Integration identifier

    Returns:
        Integration details

    Raises:
        ValueError: If integration not found
    """
    integration = integrations.get_integration(integration_id)
    if not integration:
        raise ValueError(f"Integration not found: {integration_id}")

    return integration


def handle_integrations_list(status: str | None = None) -> dict[str, Any]:
    """Handle GET /integrations request.

    Args:
        status: Optional status filter

    Returns:
        List of integrations
    """
    items = integrations.list_integrations(status=status)

    return {
        "integrations": items,
        "count": len(items),
        "status_filter": status,
    }


def check_integration_access(
    integration_id: str,
    target: str,
    correlation_id: str | None = None,
) -> bool:
    """Check if a target is authorized for an integration.

    Args:
        integration_id: Integration identifier
        target: Target endpoint to check
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if access is authorized, False otherwise
    """
    authorized = integrations.check_target_authorized(integration_id, target)

    if not authorized:
        # Emit denial audit event
        if correlation_id:
            corr_id = correlation_id
        else:
            with correlation.new_correlation_context() as corr_id:
                pass  # Just get the correlation ID
        event = evidence.construct_integration_denial_event(
            integration_id=integration_id,
            target=target,
            reason="Target not in approved list or integration expired/inactive",
            correlation_id=corr_id,
        )
        logger.warning(f"Integration access denied audit event: {event['id']}")

    return authorized
