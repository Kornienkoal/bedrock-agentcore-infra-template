"""Least-privilege analyzer utilities."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any, cast

logger = logging.getLogger(__name__)


def compute_least_privilege_score(policy_documents: Iterable[Mapping[str, object]]) -> float:
    """Compute least-privilege score from policy documents.

    Score ranges from 0 (worst) to 100 (best). Formula:
    - Base score starts at 100
    - Deduct 5 points per wildcard action
    - Deduct 10 points per wildcard resource
    - Bonus for narrow scoped resources

    Args:
        policy_documents: IAM policy documents (JSON format)

    Returns:
        Score from 0.0 to 100.0
    """
    score = 100.0
    wildcard_action_count = 0
    wildcard_resource_count = 0
    narrow_resource_count = 0
    total_statements = 0

    for doc in policy_documents:
        statements = doc.get("Statement", [])
        if not isinstance(statements, list):
            statements = [statements]

        for stmt in statements:
            stmt_dict = cast(dict[str, Any], stmt)
            if stmt_dict.get("Effect") != "Allow":
                continue

            total_statements += 1

            # Check actions for wildcards
            actions = stmt_dict.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]

            for action in actions:
                if "*" in str(action):
                    wildcard_action_count += 1

            # Check resource scope
            resources = stmt_dict.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]

            for resource in resources:
                res_str = str(resource)
                if res_str == "*":
                    wildcard_resource_count += 1
                elif ":" in res_str and "*" not in res_str:
                    narrow_resource_count += 1

    # Apply penalties
    score -= wildcard_action_count * 5
    score -= wildcard_resource_count * 10

    # Apply bonus for narrow resources (up to +10)
    if total_statements > 0:
        narrow_ratio = narrow_resource_count / total_statements
        score += min(10, narrow_ratio * 10)

    return max(0.0, min(100.0, score))


def detect_orphan_principals(
    principals: Iterable[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Identify principals that lack required ownership metadata.

    A principal is considered orphaned if:
    - Missing 'owner' field or owner is 'unknown'
    - Missing 'purpose' field or purpose is empty

    Args:
        principals: List of principal records

    Returns:
        List of orphaned principals
    """
    orphans = []

    for principal in principals:
        owner_val = principal.get("owner", "unknown")
        owner = str(owner_val).strip().lower() if owner_val else "unknown"
        purpose_val = principal.get("purpose", "")
        purpose = str(purpose_val).strip() if purpose_val else ""

        if owner in ("unknown", "", "none") or not purpose:
            orphans.append(principal)
            logger.info(
                f"Orphan detected: {principal.get('id')} (owner={owner}, purpose={bool(purpose)})"
            )

    return orphans


def compute_risk_rating(principal: Mapping[str, object]) -> str:
    """Compute risk rating based on policy footprint and usage patterns.

    Args:
        principal: Principal record with policy metadata

    Returns:
        Risk rating: LOW, MODERATE, or HIGH
    """
    # Extract risk factors
    wildcard_actions_val = principal.get("wildcard_actions", [])
    wildcard_actions = wildcard_actions_val if isinstance(wildcard_actions_val, list) else []
    scope_val = principal.get("resource_scope_wideness", "NARROW")
    scope = str(scope_val) if scope_val else "NARROW"
    inactive = bool(principal.get("inactive", False))
    score_val = principal.get("least_privilege_score", 100.0)
    least_privilege_score = float(score_val) if isinstance(score_val, (int, float)) else 100.0

    # Risk scoring
    risk_score = 0

    if len(wildcard_actions) > 5:
        risk_score += 3
    elif len(wildcard_actions) > 0:
        risk_score += 1

    if scope == "BROAD":
        risk_score += 3
    elif scope == "MODERATE":
        risk_score += 1

    if inactive:
        risk_score += 2

    if least_privilege_score < 50:
        risk_score += 2
    elif least_privilege_score < 80:
        risk_score += 1

    # Map to rating
    if risk_score >= 6:
        return "HIGH"
    elif risk_score >= 3:
        return "MODERATE"
    else:
        return "LOW"
