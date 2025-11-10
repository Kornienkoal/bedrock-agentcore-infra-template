"""Emergency revocation workflows and propagation tracking."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# In-memory storage for revocations (future: move to DynamoDB/SSM)
_revocations_registry: dict[str, dict[str, Any]] = {}
_registry_file: Path | None = None

# SLA target in seconds (configurable)
DEFAULT_SLA_TARGET_SECONDS = 300  # 5 minutes


def initialize_registry(file_path: str | Path | None = None) -> None:
    """Initialize the revocation registry storage.

    Args:
        file_path: Optional file path for persistent storage (JSON)
    """
    global _registry_file
    if file_path:
        _registry_file = Path(file_path)
        if _registry_file.exists():
            _load_registry_from_file()


def _load_registry_from_file() -> None:
    """Load revocation registry from file."""
    if not _registry_file or not _registry_file.exists():
        return

    try:
        with _registry_file.open("r") as f:
            data = json.load(f)
            _revocations_registry.update(data)
            logger.info(f"Loaded {len(data)} revocations from {_registry_file}")
    except Exception as e:
        logger.error(f"Failed to load revocation registry: {e}")


def _save_registry_to_file() -> None:
    """Save revocation registry to file."""
    if not _registry_file:
        return

    try:
        _registry_file.parent.mkdir(parents=True, exist_ok=True)
        with _registry_file.open("w") as f:
            json.dump(_revocations_registry, f, indent=2, default=str)
            logger.info(f"Saved {len(_revocations_registry)} revocations to {_registry_file}")
    except Exception as e:
        logger.error(f"Failed to save revocation registry: {e}")


def create_revocation_request(payload: dict[str, Any]) -> str:
    """Initiate a revocation request and return its identifier.

    Args:
        payload: Revocation request with subjectType, subjectId, scope, reason

    Returns:
        Revocation identifier (UUID)

    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ["subjectType", "subjectId", "scope"]
    for field in required_fields:
        if field not in payload:
            raise ValueError(f"Missing required field: {field}")

    # Validate subjectType
    valid_types = ["user", "integration", "tool", "agent", "principal"]
    if payload["subjectType"] not in valid_types:
        raise ValueError(f"Invalid subjectType. Must be one of: {valid_types}")

    # Validate scope
    valid_scopes = ["user_access", "tool_access", "integration_access", "principal_assume"]
    if payload["scope"] not in valid_scopes:
        raise ValueError(f"Invalid scope. Must be one of: {valid_scopes}")

    revocation_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC)

    revocation = {
        "id": revocation_id,
        "subject_type": payload["subjectType"],
        "subject_id": payload["subjectId"],
        "scope": payload["scope"],
        "reason": payload.get("reason", ""),
        "initiated_by": payload.get("initiatedBy", "unknown"),
        "initiated_at": timestamp.isoformat(),
        "propagated_at": None,
        "status": "pending",
        "sla_target_seconds": DEFAULT_SLA_TARGET_SECONDS,
        "propagation_latency_ms": None,
    }

    _revocations_registry[revocation_id] = revocation
    _save_registry_to_file()

    logger.info(
        f"Revocation created: {revocation_id} ({payload['subjectType']}/{payload['subjectId']})"
    )
    return revocation_id


def get_revocation_status(revocation_id: str) -> dict[str, Any]:
    """Retrieve the current status for a revocation.

    Args:
        revocation_id: Revocation identifier

    Returns:
        Revocation record

    Raises:
        ValueError: If revocation not found
    """
    if revocation_id not in _revocations_registry:
        raise ValueError(f"Revocation not found: {revocation_id}")

    return _revocations_registry[revocation_id]


def mark_revocation_propagated(revocation_id: str) -> dict[str, Any]:
    """Mark a revocation as propagated and compute latency metrics.

    Args:
        revocation_id: Revocation identifier

    Returns:
        Updated revocation record with SLA metrics

    Raises:
        ValueError: If revocation not found or already propagated
    """
    if revocation_id not in _revocations_registry:
        raise ValueError(f"Revocation not found: {revocation_id}")

    revocation = _revocations_registry[revocation_id]

    if revocation["status"] == "complete":
        raise ValueError(f"Revocation already propagated: {revocation_id}")

    propagated_at = datetime.now(UTC)
    initiated_at = datetime.fromisoformat(revocation["initiated_at"])

    # Calculate latency in milliseconds
    latency_seconds = (propagated_at - initiated_at).total_seconds()
    latency_ms = int(latency_seconds * 1000)

    # Check SLA
    sla_met = latency_seconds <= revocation["sla_target_seconds"]
    sla_status = "met" if sla_met else "breached"

    # Update revocation
    revocation.update(
        {
            "propagated_at": propagated_at.isoformat(),
            "status": "complete",
            "propagation_latency_ms": latency_ms,
            "sla_met": sla_met,
            "sla_status": sla_status,
        }
    )

    _save_registry_to_file()

    logger.info(f"Revocation propagated: {revocation_id} latency={latency_ms}ms SLA={sla_status}")

    return revocation


def mark_revocation_failed(revocation_id: str, error: str) -> dict[str, Any]:
    """Mark a revocation as failed.

    Args:
        revocation_id: Revocation identifier
        error: Error message

    Returns:
        Updated revocation record

    Raises:
        ValueError: If revocation not found
    """
    if revocation_id not in _revocations_registry:
        raise ValueError(f"Revocation not found: {revocation_id}")

    revocation = _revocations_registry[revocation_id]
    revocation.update({"status": "failed", "error": error})

    _save_registry_to_file()

    logger.error(f"Revocation failed: {revocation_id} - {error}")

    return revocation


def list_revocations(
    status: str | None = None, subject_type: str | None = None
) -> list[dict[str, Any]]:
    """List all revocations, optionally filtered by status or subject type.

    Args:
        status: Optional status filter (pending, complete, failed)
        subject_type: Optional subject type filter

    Returns:
        List of revocation records
    """
    revocations = list(_revocations_registry.values())

    if status:
        revocations = [r for r in revocations if r["status"] == status]

    if subject_type:
        revocations = [r for r in revocations if r["subject_type"] == subject_type]

    return revocations


def compute_sla_metrics() -> dict[str, Any]:
    """Compute SLA metrics across all revocations.

    Returns:
        Dictionary with SLA metrics (total, met, breached, avg_latency_ms)
    """
    complete_revocations = [r for r in _revocations_registry.values() if r["status"] == "complete"]

    if not complete_revocations:
        return {
            "total_revocations": 0,
            "sla_met": 0,
            "sla_breached": 0,
            "sla_met_percentage": 0.0,
            "avg_latency_ms": 0,
            "max_latency_ms": 0,
            "min_latency_ms": 0,
        }

    latencies = [r["propagation_latency_ms"] for r in complete_revocations]
    sla_targets = [r["sla_target_seconds"] * 1000 for r in complete_revocations]

    met_count = sum(
        1
        for r, target in zip(complete_revocations, sla_targets, strict=True)
        if r["propagation_latency_ms"] <= target
    )
    breached_count = len(complete_revocations) - met_count

    return {
        "total_revocations": len(complete_revocations),
        "sla_met_count": met_count,
        "sla_breached_count": breached_count,
        "sla_compliance_rate": (met_count / len(complete_revocations)) * 100,
        "avg_latency_ms": sum(latencies) // len(latencies),
        "max_latency_ms": max(latencies),
        "min_latency_ms": min(latencies),
    }


def emit_sla_metric() -> dict[str, Any]:
    """Emit SLA compliance metric for CloudWatch.

    Returns:
        CloudWatch-ready metric record
    """
    metrics = compute_sla_metrics()

    metric = {
        "metric_name": "RevocationSLACompliance",
        "namespace": "AgentCoreGovernance",
        "value": metrics["sla_compliance_rate"],
        "dimensions": {
            "Service": "Revocation",
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }

    logger.info(f"SLA metric emitted: {metrics['sla_compliance_rate']:.1f}% compliance")
    return metric


def is_subject_revoked(subject_type: str, subject_id: str) -> bool:
    """Check if a subject has an active revocation.

    Args:
        subject_type: Type of subject (user, integration, tool, agent, principal)
        subject_id: Subject identifier

    Returns:
        True if subject has active revocation (pending or complete)
    """
    for revocation in _revocations_registry.values():
        if (
            revocation["subject_type"] == subject_type
            and revocation["subject_id"] == subject_id
            and revocation["status"] in ["pending", "complete"]
        ):
            return True

    return False
