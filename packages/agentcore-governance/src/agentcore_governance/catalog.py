"""Catalog aggregation utilities for governance reporting."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, MutableMapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def fetch_principal_catalog(
    *, environments: Iterable[str] | None = None
) -> list[dict[str, object]]:
    """Return a normalized catalog of principals from IAM roles.

    Args:
        environments: Optional filter for environment tags

    Returns:
        List of principal records with metadata
    """
    iam = boto3.client("iam")
    principals = []

    try:
        paginator = iam.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page["Roles"]:
                # Parse tags
                try:
                    tags_response = iam.list_role_tags(RoleName=role["RoleName"])
                    tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("Tags", [])}
                except ClientError as e:
                    logger.warning(f"Could not fetch tags for role {role['RoleName']}: {e}")
                    tags = {}

                # Filter by environment if specified
                role_env = tags.get("Environment", tags.get("environment", "unknown"))
                if environments and role_env not in environments:
                    continue

                # Fetch attached policies for footprint
                try:
                    attached_policies_response = iam.list_attached_role_policies(
                        RoleName=role["RoleName"]
                    )
                    attached_policies = [
                        p["PolicyArn"]
                        for p in attached_policies_response.get("AttachedPolicies", [])
                    ]
                except ClientError:
                    attached_policies = []

                principal = {
                    "id": role["Arn"],
                    "type": _infer_principal_type(role["RoleName"], tags),
                    "environment": role_env,
                    "namespace": tags.get("Namespace", tags.get("namespace", "unknown")),
                    "owner": tags.get("Owner", tags.get("owner", "unknown")),
                    "purpose": tags.get(
                        "Purpose", tags.get("purpose", role.get("Description", ""))
                    ),
                    "created_at": role["CreateDate"].isoformat(),
                    "last_used_at": _extract_last_used(role),
                    "risk_rating": "UNKNOWN",  # Computed later by analyzer
                    "tags": tags,
                    "status": "active",
                    "attached_policies": attached_policies,
                }
                principals.append(principal)

    except ClientError as e:
        logger.error(f"Failed to fetch IAM roles: {e}")
        raise

    return principals


def _infer_principal_type(role_name: str, tags: dict[str, str]) -> str:
    """Infer principal type from role name and tags."""
    role_lower = role_name.lower()
    if "execution" in role_lower or "runtime" in role_lower:
        return "execution_role"
    elif "gateway" in role_lower:
        return "gateway_role"
    elif "provisioner" in role_lower or "terraform" in role_lower:
        return "provisioner_role"
    elif "tool" in role_lower:
        return "tool_role"
    elif "knowledge" in role_lower or "memory" in role_lower:
        return "knowledge_role"
    return tags.get("Type", "execution_role")


def _extract_last_used(role: dict[str, Any]) -> str | None:
    """Extract last used timestamp from role metadata."""
    role_last_used = role.get("RoleLastUsed")
    if role_last_used and "LastUsedDate" in role_last_used:
        last_used_date = role_last_used["LastUsedDate"]
        if hasattr(last_used_date, "isoformat"):
            return str(last_used_date.isoformat())
    return None


def summarize_policy_footprint(
    policy_documents: Iterable[Mapping[str, object]],
) -> MutableMapping[str, object]:
    """Compute policy footprint summary from IAM policy documents.

    Args:
        policy_documents: List of IAM policy documents (JSON)

    Returns:
        Summary with action count, wildcards, and scope rating
    """
    all_actions: set[str] = set()
    wildcard_actions: list[str] = []
    wildcard_resources = 0
    total_statements = 0

    for doc in policy_documents:
        statements = doc.get("Statement", [])
        if not isinstance(statements, list):
            statements = [statements]

        for stmt in statements:
            total_statements += 1
            stmt_dict = cast(dict[str, Any], stmt)
            if stmt_dict.get("Effect") != "Allow":
                continue

            # Extract actions
            actions = stmt_dict.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]

            for action in actions:
                all_actions.add(action)
                if "*" in action:
                    wildcard_actions.append(action)

            # Check resource scope
            resources = stmt_dict.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]
            if any(r == "*" for r in resources):
                wildcard_resources += 1

    # Determine scope wideness
    if wildcard_resources > total_statements * 0.5:
        scope = "BROAD"
    elif wildcard_resources > 0:
        scope = "MODERATE"
    else:
        scope = "NARROW"

    return {
        "attached_policies": [],  # Caller should populate
        "action_count": len(all_actions),
        "wildcard_actions": wildcard_actions,
        "resource_scope_wideness": scope,
        "least_privilege_score": 0.0,  # Computed by analyzer
    }


def flag_inactive_principals(
    principals: list[dict[str, object]], inactivity_days: int = 30
) -> list[dict[str, object]]:
    """Flag principals inactive for more than specified days.

    Args:
        principals: List of principal records
        inactivity_days: Threshold for inactivity flag

    Returns:
        Updated principals with inactivity flag
    """
    threshold = datetime.now(UTC) - timedelta(days=inactivity_days)

    for principal in principals:
        last_used_val = principal.get("last_used_at")
        if not last_used_val:
            principal["inactive"] = True
            continue

        try:
            last_used_str = str(last_used_val)
            last_used = datetime.fromisoformat(last_used_str.replace("Z", "+00:00"))
            principal["inactive"] = last_used < threshold
        except (ValueError, AttributeError, TypeError):
            principal["inactive"] = True

    return principals


def export_catalog_snapshot(
    environment: str | None = None,
    include_metadata: bool = True,
) -> dict[str, Any]:
    """Export complete catalog snapshot as JSON-serializable dictionary.

    Args:
        environment: Optional environment filter
        include_metadata: Include snapshot metadata (timestamp, filters)

    Returns:
        Dictionary with principals array and optional metadata
    """
    principals = fetch_principal_catalog(environments=[environment] if environment else None)
    principals = flag_inactive_principals(principals)

    snapshot: dict[str, Any] = {
        "principals": principals,
    }

    if include_metadata:
        snapshot["metadata"] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": environment,
            "total_count": len(principals),
            "inactive_count": sum(1 for p in principals if p.get("inactive", False)),
        }

    return snapshot
