"""REST API handlers for principal catalog endpoints."""

from __future__ import annotations

import logging
from typing import Any

from agentcore_governance import analyzer, catalog

logger = logging.getLogger(__name__)


def get_principals(
    environment: str | None = None,
    owner: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Handle GET /catalog/principals request.

    Args:
        environment: Optional environment filter
        owner: Optional owner filter
        page: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        Response with principals array, pagination metadata, and filters applied
    """
    env_filter = catalog.normalize_environment_filter(environment)
    env_display = "all" if env_filter is None else list(env_filter)

    try:
        # Fetch principals from catalog
        all_principals = catalog.fetch_principal_catalog(environments=env_filter)

        # Apply owner filter if specified
        if owner:
            all_principals = [
                p for p in all_principals if str(p.get("owner", "")).lower() == owner.lower()
            ]

        # Validate ownership tags and apply fallback labeling
        all_principals = _apply_ownership_validation(all_principals)

        # Apply inactivity flagging
        all_principals = catalog.flag_inactive_principals(all_principals)

        # Compute risk ratings for each principal
        for principal in all_principals:
            # Get policy footprint if available
            policy_summary = principal.get("policy_summary", {})
            if isinstance(policy_summary, dict):
                principal["wildcard_actions"] = policy_summary.get("wildcard_actions", [])
                principal["resource_scope_wideness"] = policy_summary.get(
                    "resource_scope_wideness", "NARROW"
                )
                principal["least_privilege_score"] = policy_summary.get(
                    "least_privilege_score", 100.0
                )

            # Compute risk rating
            principal["risk_rating"] = analyzer.compute_risk_rating(principal)

        # Pagination logic
        total_count = len(all_principals)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_principals = all_principals[start_idx:end_idx]

        total_pages = (total_count + page_size - 1) // page_size

        return {
            "principals": paginated_principals,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
            "filters": {
                "environment": env_display,
                "owner": owner,
            },
        }

    except Exception as e:
        logger.error(f"Error fetching principals: {e}", exc_info=True)

        return {
            "error": str(e),
            "principals": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": 0,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
            },
            "filters": {
                "environment": env_display,
                "owner": owner,
            },
        }


def _apply_ownership_validation(principals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate ownership tags and apply fallback labeling.

    Args:
        principals: List of principal records

    Returns:
        Principals with validated ownership metadata
    """
    for principal in principals:
        owner_val = principal.get("owner")
        owner = str(owner_val).strip() if owner_val else ""

        # Apply fallback labeling for missing or invalid owners
        if not owner or owner.lower() in ("unknown", "none", "n/a", ""):
            principal["owner"] = "UNASSIGNED"
            principal["ownership_status"] = "missing"
        else:
            principal["ownership_status"] = "assigned"

        # Validate purpose field
        purpose_val = principal.get("purpose")
        purpose = str(purpose_val).strip() if purpose_val else ""

        if not purpose:
            principal["purpose"] = "No purpose documented"
            principal["purpose_status"] = "missing"
        else:
            principal["purpose_status"] = "documented"

    return principals
