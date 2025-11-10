"""Third-party integration allowlist management."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# In-memory storage for integrations (future: move to SSM/DynamoDB)
_integrations_registry: dict[str, dict[str, Any]] = {}
_registry_file: Path | None = None


def initialize_registry(file_path: str | Path | None = None) -> None:
    """Initialize the integration registry storage.

    Args:
        file_path: Optional file path for persistent storage (JSON or YAML)
    """
    global _registry_file
    if file_path:
        _registry_file = Path(file_path)
        if _registry_file.exists():
            _load_registry_from_file()


def _load_registry_from_file() -> None:
    """Load integration registry from file."""
    if not _registry_file or not _registry_file.exists():
        return

    try:
        with _registry_file.open("r") as f:
            data = json.load(f)
            _integrations_registry.update(data)
            logger.info(f"Loaded {len(data)} integrations from {_registry_file}")
    except Exception as e:
        logger.error(f"Failed to load integration registry: {e}")


def _save_registry_to_file() -> None:
    """Save integration registry to file."""
    if not _registry_file:
        return

    try:
        _registry_file.parent.mkdir(parents=True, exist_ok=True)
        with _registry_file.open("w") as f:
            json.dump(_integrations_registry, f, indent=2, default=str)
            logger.info(f"Saved {len(_integrations_registry)} integrations to {_registry_file}")
    except Exception as e:
        logger.error(f"Failed to save integration registry: {e}")


def request_integration(payload: dict[str, Any]) -> str:
    """Record an integration request and return its identifier.

    Args:
        payload: Integration request with name, justification, requestedTargets

    Returns:
        Integration identifier (UUID)

    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ["name", "justification", "requestedTargets"]
    for field in required_fields:
        if field not in payload:
            raise ValueError(f"Missing required field: {field}")

    integration_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC)

    integration = {
        "id": integration_id,
        "name": payload["name"],
        "justification": payload["justification"],
        "requested_targets": payload["requestedTargets"],
        "approved_targets": [],
        "approved_by": None,
        "approved_at": None,
        "expires_at": None,
        "status": "pending",
        "requested_at": timestamp.isoformat(),
    }

    _integrations_registry[integration_id] = integration
    _save_registry_to_file()

    logger.info(f"Integration request created: {integration_id} ({payload['name']})")
    return integration_id


def approve_integration(
    integration_id: str,
    *,
    approved_targets: list[str],
    expiry_days: int | None,
    approved_by: str,
) -> None:
    """Approve a pending integration request.

    Args:
        integration_id: Integration identifier
        approved_targets: List of approved target endpoints
        expiry_days: Optional number of days until expiry
        approved_by: Identity of the approver

    Raises:
        ValueError: If integration not found or not in pending status
    """
    if integration_id not in _integrations_registry:
        raise ValueError(f"Integration not found: {integration_id}")

    integration = _integrations_registry[integration_id]

    if integration["status"] != "pending":
        raise ValueError(f"Integration not in pending status: {integration['status']}")

    timestamp = datetime.now(UTC)
    expires_at = None
    if expiry_days and expiry_days > 0:
        expires_at = timestamp + timedelta(days=expiry_days)

    integration.update(
        {
            "approved_targets": approved_targets,
            "approved_by": approved_by,
            "approved_at": timestamp.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "status": "active",
        }
    )

    _save_registry_to_file()

    logger.info(
        f"Integration approved: {integration_id} "
        f"by {approved_by} with {len(approved_targets)} targets"
    )


def get_integration(integration_id: str) -> dict[str, Any] | None:
    """Retrieve an integration by ID.

    Args:
        integration_id: Integration identifier

    Returns:
        Integration record or None if not found
    """
    return _integrations_registry.get(integration_id)


def list_integrations(status: str | None = None) -> list[dict[str, Any]]:
    """List all integrations, optionally filtered by status.

    Args:
        status: Optional status filter (pending, active, expired, revoked, denied)

    Returns:
        List of integration records
    """
    integrations = list(_integrations_registry.values())

    if status:
        integrations = [i for i in integrations if i["status"] == status]

    return integrations


def check_target_authorized(integration_id: str, target: str) -> bool:
    """Check if a target is authorized for an integration.

    Args:
        integration_id: Integration identifier
        target: Target endpoint to check

    Returns:
        True if target is authorized and integration is active
    """
    integration = get_integration(integration_id)
    if not integration:
        return False

    if integration["status"] != "active":
        return False

    # Check expiry
    if integration["expires_at"]:
        expires_at = datetime.fromisoformat(integration["expires_at"])
        if datetime.now(UTC) > expires_at:
            # Mark as expired
            integration["status"] = "expired"
            _save_registry_to_file()
            logger.warning(f"Integration expired: {integration_id}")
            return False

    return target in integration.get("approved_targets", [])


def mark_expired_integrations() -> int:
    """Mark integrations with past expiry dates as expired.

    Returns:
        Number of integrations marked as expired
    """
    now = datetime.now(UTC)
    count = 0

    for integration in _integrations_registry.values():
        if integration["status"] != "active":
            continue

        expires_at_str = integration.get("expires_at")
        if not expires_at_str:
            continue

        expires_at = datetime.fromisoformat(expires_at_str)
        if now > expires_at:
            integration["status"] = "expired"
            count += 1
            logger.info(f"Marked integration as expired: {integration['id']}")

    if count > 0:
        _save_registry_to_file()

    return count


def revoke_integration(integration_id: str, reason: str | None = None) -> None:
    """Revoke an active integration.

    Args:
        integration_id: Integration identifier
        reason: Optional revocation reason

    Raises:
        ValueError: If integration not found
    """
    if integration_id not in _integrations_registry:
        raise ValueError(f"Integration not found: {integration_id}")

    integration = _integrations_registry[integration_id]
    integration["status"] = "revoked"
    integration["revoked_at"] = datetime.now(UTC).isoformat()
    if reason:
        integration["revocation_reason"] = reason

    _save_registry_to_file()

    logger.info(f"Integration revoked: {integration_id}")
