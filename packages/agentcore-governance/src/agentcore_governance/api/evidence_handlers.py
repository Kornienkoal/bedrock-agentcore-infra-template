"""REST API handlers for evidence pack endpoints."""

from __future__ import annotations

import logging
from typing import Any

from agentcore_governance import evidence

logger = logging.getLogger(__name__)


def generate_evidence_pack(
    hours_back: int = 24,
    include_decisions: bool = True,
    include_catalog: bool = True,
) -> dict[str, Any]:
    """Handle POST /evidence-pack request.

    Generates comprehensive evidence pack with catalog snapshot,
    audit events, policy decisions, and conformance metrics.

    Args:
        hours_back: Time window for audit events (hours)
        include_decisions: Whether to include policy decision history
        include_catalog: Whether to include principal catalog snapshot

    Returns:
        Response with evidence pack metadata and download information
    """
    try:
        # Generate base evidence pack
        pack = evidence.build_evidence_pack({"hours_back": hours_back})

        # Enhance with additional components
        if include_decisions:
            pack["decisions"] = _fetch_recent_decisions(hours_back)

        if include_catalog:
            pack["catalog_snapshot"] = _fetch_catalog_snapshot()

        # Add correlation chain reconstruction capability
        pack["reconstruction_available"] = True
        pack["reconstruction_endpoint"] = "/evidence-pack/reconstruct"

        logger.info(
            f"Generated evidence pack {pack['id']} covering {hours_back}h "
            f"with {pack.get('principal_snapshot_count', 0)} principals"
        )

        return {
            "evidence_pack": pack,
            "status": 200,
        }

    except Exception as e:
        logger.error(f"Error generating evidence pack: {e}", exc_info=True)
        return {
            "error": f"Failed to generate evidence pack: {e!s}",
            "status": 500,
        }


def reconstruct_trace(correlation_id: str) -> dict[str, Any]:
    """Reconstruct complete audit trace for correlation ID.

    Args:
        correlation_id: Correlation identifier to trace

    Returns:
        Complete event chain with integrity verification
    """
    try:
        # Reconstruct correlation chain
        reconstruction = evidence.reconstruct_correlation_chain(correlation_id)

        # Verify integrity
        integrity_status = "verified" if not reconstruction["integrity_failures"] else "failed"

        return {
            "reconstruction": reconstruction,
            "integrity_status": integrity_status,
            "status": 200,
        }

    except Exception as e:
        logger.error(f"Error reconstructing trace: {e}", exc_info=True)
        return {
            "error": f"Failed to reconstruct trace: {e!s}",
            "status": 500,
        }


def validate_evidence_integrity(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate integrity hashes for a collection of events.

    Args:
        events: List of audit events to validate

    Returns:
        Validation report with pass/fail status and details
    """
    try:
        from agentcore_governance import integrity

        validation_results = []
        failed_count = 0

        for event in events:
            event_id = event.get("id", "unknown")
            stored_hash = event.get("integrity_hash")

            if not stored_hash:
                validation_results.append(
                    {
                        "event_id": event_id,
                        "status": "missing_hash",
                        "valid": False,
                    }
                )
                failed_count += 1
                continue

            # Recompute hash based on event type
            # This is simplified - production would have event-type-specific logic
            event_type = event.get("event_type", "")
            hash_fields = _extract_hash_fields(event, event_type)

            computed_hash = integrity.compute_integrity_hash(hash_fields)
            is_valid = computed_hash == stored_hash

            validation_results.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "status": "valid" if is_valid else "tampered",
                    "valid": is_valid,
                    "stored_hash": stored_hash[:16] + "...",
                    "computed_hash": computed_hash[:16] + "...",
                }
            )

            if not is_valid:
                failed_count += 1

        total_count = len(events)
        passed_count = total_count - failed_count

        return {
            "total_events": total_count,
            "passed": passed_count,
            "failed": failed_count,
            "validation_results": validation_results,
            "overall_status": "passed" if failed_count == 0 else "failed",
            "status": 200,
        }

    except Exception as e:
        logger.error(f"Error validating integrity: {e}", exc_info=True)
        return {
            "error": f"Failed to validate integrity: {e!s}",
            "status": 500,
        }


def _fetch_recent_decisions(hours_back: int) -> dict[str, Any]:
    """Fetch recent policy decisions for evidence pack.

    Args:
        hours_back: Time window in hours

    Returns:
        Decision summary with counts and sample
    """
    try:
        from agentcore_governance.api import decision_handlers

        response = decision_handlers.list_decisions(hours_back=hours_back, limit=1000)

        status_code = response.get("status")
        if isinstance(status_code, int) and status_code == 200:
            decisions = response.get("decisions", [])
            allow_count = sum(1 for d in decisions if d.get("effect") == "allow")
            deny_count = sum(1 for d in decisions if d.get("effect") == "deny")

            return {
                "total_decisions": len(decisions),
                "allow_count": allow_count,
                "deny_count": deny_count,
                "sample_decisions": decisions[:10],
            }
        return {"total_decisions": 0, "allow_count": 0, "deny_count": 0}

    except Exception as e:
        logger.warning(f"Could not fetch decisions: {e}")
        return {"error": str(e)}


def _fetch_catalog_snapshot() -> dict[str, Any]:
    """Fetch principal catalog snapshot for evidence pack.

    Returns:
        Catalog summary with counts and high-risk principals
    """
    try:
        from agentcore_governance import catalog

        principals = catalog.fetch_principal_catalog()

        high_risk = []
        for p in principals:
            score = p.get("least_privilege_score", 100)
            if p.get("risk_rating") == "HIGH" or (
                isinstance(score, (int, float)) and float(score) < 50
            ):
                high_risk.append(p)

        return {
            "total_principals": len(principals),
            "high_risk_count": len(high_risk),
            "high_risk_sample": high_risk[:5],
        }

    except Exception as e:
        logger.warning(f"Could not fetch catalog: {e}")
        return {"error": str(e)}


def _extract_hash_fields(event: dict[str, Any], event_type: str) -> list[str]:
    """Extract fields for hash computation based on event type.

    Args:
        event: Event dictionary
        event_type: Type of event

    Returns:
        List of field values for hashing
    """
    # Common fields
    fields = [
        event.get("id", ""),
        event.get("timestamp", ""),
    ]

    # Event-specific fields
    if event_type == "authorization_decision":
        fields.extend(
            [
                event.get("agent_id", ""),
                event.get("tool_id", ""),
                event.get("effect", ""),
                event.get("reason", ""),
            ]
        )
    elif event_type == "revocation_request":
        fields.extend(
            [
                event.get("revocation_id", ""),
                event.get("subject_type", ""),
                event.get("subject_id", ""),
                event.get("scope", ""),
                event.get("reason", ""),
                event.get("initiated_by", ""),
            ]
        )
    elif event_type == "policy_decision":
        fields.extend(
            [
                event.get("subject_id", ""),
                event.get("action", ""),
                event.get("resource", ""),
                event.get("effect", ""),
            ]
        )
    else:
        # Generic approach: use all string/number fields except integrity_hash
        for key, value in event.items():
            if key != "integrity_hash" and isinstance(value, (str, int, float)):
                fields.append(str(value))

    return fields
