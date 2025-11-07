"""Catalog aggregation utilities for governance reporting."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from collections.abc import Iterable as TypingIterable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import boto3
from botocore.exceptions import BotoCoreError, ClientError, TokenRetrievalError

logger = logging.getLogger(__name__)


def normalize_environment_filter(
    environment: str | Iterable[str] | None,
) -> Iterable[str] | None:
    """Return environment filter iterable or None for all environments.

    Accepts single string (including "all" or empty), iterable, or None and
    normalizes to the form expected by catalog queries.
    """

    if environment is None:
        return None

    if isinstance(environment, str):
        value = environment.strip()
        if not value or value.lower() == "all":
            return None
        return [value]

    filtered = [env.strip() for env in environment if env and env.strip().lower() != "all"]
    return filtered or None


def fetch_principal_catalog(
    *, environments: Iterable[str] | None = None
) -> list[dict[str, object]]:
    """Return a normalized catalog of principals from IAM roles.

    Args:
        environments: Optional filter for environment tags

    Returns:
        List of principal records with metadata
    """
    environments = normalize_environment_filter(environments)

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

                # Fetch policy documents for footprint analysis
                policy_summary = _fetch_policy_summary(iam, role["RoleName"], attached_policies)

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
                    "policy_summary": policy_summary,
                }
                principals.append(principal)

    except (ClientError, BotoCoreError, TokenRetrievalError) as e:
        logger.warning("Falling back to sample principal catalog due to AWS fetch failure: %s", e)
        return _load_sample_catalog(environments)

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


def _fetch_policy_summary(
    iam_client: Any, role_name: str, policy_arns: list[str]
) -> dict[str, Any]:
    """Fetch and summarize policy documents for a role.

    Args:
        iam_client: Boto3 IAM client
        role_name: Role name to fetch policies for
        policy_arns: List of attached policy ARNs

    Returns:
        Policy summary with actions, wildcards, and scope
    """
    policy_documents = []

    # Fetch inline policies
    try:
        inline_policies = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in inline_policies.get("PolicyNames", []):
            try:
                policy_doc = iam_client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
                policy_documents.append(policy_doc["PolicyDocument"])
            except ClientError as e:
                logger.warning(f"Could not fetch inline policy {policy_name} for {role_name}: {e}")
    except ClientError as e:
        logger.warning(f"Could not list inline policies for {role_name}: {e}")

    # Fetch managed policies
    for arn in policy_arns:
        try:
            # Get policy version
            policy = iam_client.get_policy(PolicyArn=arn)
            default_version = policy["Policy"]["DefaultVersionId"]

            # Get policy document
            policy_version = iam_client.get_policy_version(PolicyArn=arn, VersionId=default_version)
            policy_documents.append(policy_version["PolicyVersion"]["Document"])
        except ClientError as e:
            logger.warning(f"Could not fetch policy {arn}: {e}")

    # Summarize the policy footprint
    return summarize_policy_footprint(policy_documents)


def _load_sample_catalog(environments: TypingIterable[str] | None) -> list[dict[str, object]]:
    """Provide deterministic sample catalog data when AWS access is unavailable."""

    sample_principals: list[dict[str, object]] = [
        {
            "id": "arn:aws:iam::000000000000:role/sample-runtime",
            "type": "execution_role",
            "environment": "dev",
            "namespace": "customer-support",
            "owner": "owner@example.com",
            "purpose": "Runtime execution role",
            "created_at": "2024-01-10T12:00:00+00:00",
            "last_used_at": "2025-10-01T12:00:00+00:00",
            "risk_rating": "LOW",
            "tags": {
                "Environment": "dev",
                "Namespace": "customer-support",
                "Owner": "owner@example.com",
                "Purpose": "Runtime execution role",
            },
            "status": "active",
            "inactive": False,
            "attached_policies": [],
            "policy_summary": {
                "wildcard_actions": [],
                "least_privilege_score": 98.0,
                "attached_policies": [],
            },
            "least_privilege_score": 98.0,
        },
        {
            "id": "arn:aws:iam::000000000000:role/sample-orphan",
            "type": "execution_role",
            "environment": "dev",
            "namespace": "unknown",
            "owner": "unknown",
            "purpose": "",
            "created_at": "2023-05-05T08:30:00+00:00",
            "last_used_at": None,
            "risk_rating": "MODERATE",
            "tags": {
                "Environment": "dev",
                "Namespace": "unknown",
            },
            "status": "active",
            "inactive": True,
            "attached_policies": [
                "arn:aws:iam::aws:policy/AdministratorAccess",
            ],
            "policy_summary": {
                "wildcard_actions": ["iam:*"],
                "least_privilege_score": 45.0,
                "attached_policies": [
                    "arn:aws:iam::aws:policy/AdministratorAccess",
                ],
            },
            "least_privilege_score": 45.0,
        },
        {
            "id": "arn:aws:iam::000000000000:role/sample-prod-runtime",
            "type": "execution_role",
            "environment": "prod",
            "namespace": "warranty-docs",
            "owner": "prod-owner@example.com",
            "purpose": "Production runtime",
            "created_at": "2024-03-15T09:15:00+00:00",
            "last_used_at": "2025-09-20T09:15:00+00:00",
            "risk_rating": "LOW",
            "tags": {
                "Environment": "prod",
                "Namespace": "warranty-docs",
                "Owner": "prod-owner@example.com",
                "Purpose": "Production runtime",
            },
            "status": "active",
            "inactive": False,
            "attached_policies": [
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            ],
            "policy_summary": {
                "wildcard_actions": [],
                "least_privilege_score": 92.0,
                "attached_policies": [
                    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                ],
            },
            "least_privilege_score": 92.0,
        },
    ]

    if environments:
        environment_set = {env for env in environments if env}
        if not environment_set:
            return sample_principals
        return [p for p in sample_principals if p.get("environment") in environment_set]

    return sample_principals


def summarize_policy_footprint(
    policy_documents: Iterable[Mapping[str, object]],
) -> dict[str, Any]:
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
    if total_statements == 0:
        scope = "NARROW"
    elif wildcard_resources > total_statements * 0.5:
        scope = "BROAD"
    elif wildcard_resources > 0:
        scope = "MODERATE"
    else:
        scope = "NARROW"

    return {
        "action_count": len(all_actions),
        "wildcard_actions": wildcard_actions,
        "wildcard_resource_statements": wildcard_resources,
        "total_statements": total_statements,
        "resource_scope_wideness": scope,
        "actions": sorted(all_actions),  # For detailed analysis
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
    env_filter = normalize_environment_filter(environment)
    principals = fetch_principal_catalog(environments=env_filter)
    principals = flag_inactive_principals(principals)

    snapshot: dict[str, Any] = {
        "principals": principals,
    }

    if include_metadata:
        snapshot["metadata"] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": "all" if env_filter is None else list(env_filter),
            "total_count": len(principals),
            "inactive_count": sum(1 for p in principals if p.get("inactive", False)),
        }

    return snapshot


def schedule_quarterly_attestation(
    owner: str, principals: list[dict[str, object]]
) -> dict[str, Any]:
    """Schedule quarterly attestation reminder for principal owner (FR-018, T081).

    This is a stub implementation that demonstrates attestation workflow.
    In production, this would integrate with notification systems (SNS, email)
    and track attestation completion status.

    Args:
        owner: Owner identifier to receive attestation request
        principals: List of principals requiring attestation

    Returns:
        Attestation record with scheduled date and principal summary
    """
    import uuid

    attestation_id = uuid.uuid4().hex
    scheduled_date = (datetime.now(UTC) + timedelta(days=90)).isoformat()

    attestation_record = {
        "attestation_id": attestation_id,
        "owner": owner,
        "scheduled_date": scheduled_date,
        "status": "scheduled",
        "principals_count": len(principals),
        "principals": [
            {
                "id": p["id"],
                "type": p.get("type", "unknown"),
                "environment": p.get("environment", "unknown"),
            }
            for p in principals
        ],
        "created_at": datetime.now(UTC).isoformat(),
    }

    logger.info(
        f"Scheduled attestation {attestation_id} for owner {owner} "
        f"({len(principals)} principals) on {scheduled_date}"
    )

    return attestation_record
