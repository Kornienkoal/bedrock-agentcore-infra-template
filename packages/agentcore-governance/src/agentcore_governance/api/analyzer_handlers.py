"""REST API handlers for analyzer endpoints."""

from __future__ import annotations

import logging
from typing import Any

from agentcore_governance import analyzer, catalog

logger = logging.getLogger(__name__)


def get_least_privilege_report(
    environment: str | None = None,
    threshold: float = 95.0,
) -> dict[str, Any]:
    """Handle GET /analyzer/least-privilege request.

    Generates comprehensive least-privilege conformance report with
    per-principal scores and aggregate metrics.

    Args:
        environment: Optional environment filter
        threshold: Minimum acceptable least-privilege score (default 95.0)

    Returns:
        Response with conformance metrics, failing principals, and recommendations
    """
    env_filter = catalog.normalize_environment_filter(environment)
    env_display = "all" if env_filter is None else list(env_filter)

    try:
        # Fetch principal catalog
        principals = catalog.fetch_principal_catalog(environments=env_filter)

        # Compute least-privilege scores for each principal
        scored_principals: list[dict[str, Any]] = []
        for principal in principals:
            # Get attached policies for scoring
            # policy_summary is a dict with attached_policies list
            policy_summary = principal.get("policy_summary", {})
            attached_policies = (
                policy_summary.get("attached_policies", [])
                if isinstance(policy_summary, dict)
                else []
            )

            if attached_policies and isinstance(attached_policies, list):
                # Convert policy names to mock policy documents for scoring
                # In production, would fetch actual policy documents
                score = analyzer.compute_least_privilege_score([])
                # Use pre-computed score if available
                if isinstance(policy_summary, dict) and "least_privilege_score" in policy_summary:
                    score = policy_summary["least_privilege_score"]
                principal["least_privilege_score"] = score
            else:
                principal["least_privilege_score"] = principal.get("least_privilege_score", 0.0)

            scored_principals.append(principal)

        # Compute aggregate metrics
        total_count = len(scored_principals)
        if total_count == 0:
            return {
                "conformance_score": 0.0,
                "total_principals": 0,
                "passing_count": 0,
                "failing_count": 0,
                "failing_principals": [],
                "threshold": threshold,
                "status": 200,
            }

        scores = [p["least_privilege_score"] for p in scored_principals]
        conformance_score = sum(scores) / total_count

        # Identify failing principals (below threshold)
        failing_principals = [
            {
                "id": p.get("id", "unknown"),
                "type": p.get("type", "unknown"),
                "owner": p.get("owner", "unowned"),
                "score": p.get("least_privilege_score", 0.0),
                "wildcard_actions": p.get("policy_summary", {}).get("wildcard_actions", [])
                if isinstance(p.get("policy_summary"), dict)
                else [],
            }
            for p in scored_principals
            if isinstance(p.get("least_privilege_score"), (int, float))
            and float(p["least_privilege_score"]) < threshold
        ]

        passing_count = total_count - len(failing_principals)

        # Generate recommendations
        recommendations = _generate_recommendations(failing_principals)

        return {
            "conformance_score": round(conformance_score, 2),
            "total_principals": total_count,
            "passing_count": passing_count,
            "failing_count": len(failing_principals),
            "threshold": threshold,
            "failing_principals": failing_principals[:50],  # Limit to first 50
            "recommendations": recommendations,
            "environment": env_display,
            "status": 200,
        }

    except Exception as e:
        logger.error(f"Error generating least-privilege report: {e}", exc_info=True)
        return {
            "error": f"Failed to generate report: {e!s}",
            "status": 500,
        }


def _generate_recommendations(failing_principals: list[dict[str, Any]]) -> list[str]:
    """Generate actionable recommendations based on failing principals.

    Args:
        failing_principals: List of principals below threshold

    Returns:
        List of recommendation strings
    """
    recommendations = []

    if not failing_principals:
        return ["All principals meet least-privilege threshold. No action required."]

    # Count common issues
    wildcard_count = sum(
        1
        for p in failing_principals
        if p.get("wildcard_actions") and len(p.get("wildcard_actions", [])) > 0
    )
    unowned_count = sum(1 for p in failing_principals if p.get("owner") == "unowned")

    if wildcard_count > 0:
        recommendations.append(
            f"{wildcard_count} principal(s) use wildcard actions. "
            "Review and scope down to specific actions where possible."
        )

    if unowned_count > 0:
        recommendations.append(
            f"{unowned_count} principal(s) lack ownership tags. "
            "Assign owners for accountability and lifecycle management."
        )

    # Identify principals with very low scores (< 50)
    critical_count = sum(
        1
        for p in failing_principals
        if isinstance(p.get("score"), (int, float)) and float(p["score"]) < 50.0
    )
    if critical_count > 0:
        recommendations.append(
            f"{critical_count} principal(s) have critically low scores (< 50). "
            "Prioritize immediate policy review and tightening."
        )

    if len(failing_principals) > 10:
        recommendations.append(
            "Large number of non-conformant principals detected. "
            "Consider implementing automated policy remediation workflows."
        )

    return recommendations


def get_orphan_principals(environment: str | None = None) -> dict[str, Any]:
    """Identify principals without ownership tags or recent usage.

    Args:
        environment: Optional environment filter

    Returns:
        List of orphaned principals with recommendations
    """
    env_filter = catalog.normalize_environment_filter(environment)
    env_display = "all" if env_filter is None else list(env_filter)

    try:
        principals = catalog.fetch_principal_catalog(environments=env_filter)

        # Detect orphans (no owner or no recent usage)
        orphans = analyzer.detect_orphan_principals(principals)

        return {
            "orphan_count": len(orphans),
            "orphans": orphans[:100],  # Limit response size
            "environment": env_display,
            "status": 200,
        }

    except Exception as e:
        logger.error(f"Error detecting orphans: {e}", exc_info=True)
        return {
            "error": f"Failed to detect orphans: {e!s}",
            "status": 500,
        }
