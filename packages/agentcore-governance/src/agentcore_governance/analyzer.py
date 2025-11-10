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
    # Extract policy summary if present
    policy_summary = principal.get("policy_summary", {})
    if isinstance(policy_summary, dict):
        wildcard_actions = policy_summary.get("wildcard_actions", [])
        scope = policy_summary.get("resource_scope_wideness", "NARROW")
        action_count = policy_summary.get("action_count", 0)
    else:
        # Fallback to old structure
        wildcard_actions_val = principal.get("wildcard_actions", [])
        wildcard_actions = wildcard_actions_val if isinstance(wildcard_actions_val, list) else []
        scope_val = principal.get("resource_scope_wideness", "NARROW")
        scope = str(scope_val) if scope_val else "NARROW"
        action_count = 0

    inactive = bool(principal.get("inactive", False))
    score_val = principal.get("least_privilege_score", 100.0)
    least_privilege_score = float(score_val) if isinstance(score_val, (int, float)) else 100.0

    # Risk scoring
    risk_score = 0

    # Wildcard actions penalty
    wildcard_count = len(wildcard_actions) if isinstance(wildcard_actions, list) else 0
    if wildcard_count > 5:
        risk_score += 3
    elif wildcard_count > 0:
        risk_score += 1

    # Broad permissions penalty
    if scope == "BROAD":
        risk_score += 3
    elif scope == "MODERATE":
        risk_score += 1

    # Excessive permissions penalty
    if action_count > 100:
        risk_score += 2
    elif action_count > 50:
        risk_score += 1

    # Inactive principal penalty
    if inactive:
        risk_score += 2

    # Least privilege score penalty
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


def enrich_principals_with_scores(
    principals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enrich principals with least-privilege scores and risk ratings.

    Args:
        principals: List of principal records with policy_summary

    Returns:
        Enriched principals with scores and ratings
    """
    for principal in principals:
        # Compute least-privilege score from policy summary
        policy_summary = principal.get("policy_summary", {})
        if isinstance(policy_summary, dict) and policy_summary:
            # Create mock policy documents from summary for scoring
            # (In real implementation, we'd store the actual docs)
            wildcard_actions = policy_summary.get("wildcard_actions", [])
            wildcard_resources = policy_summary.get("wildcard_resource_statements", 0)
            total_statements = policy_summary.get("total_statements", 0)

            # Simplified scoring based on summary
            score = 100.0
            score -= len(wildcard_actions) * 5
            score -= wildcard_resources * 10

            # Bonus for narrow scope
            if total_statements > 0 and policy_summary.get("resource_scope_wideness") == "NARROW":
                score += 10

            principal["least_privilege_score"] = max(0.0, min(100.0, score))
        else:
            principal["least_privilege_score"] = 100.0

        # Compute risk rating
        principal["risk_rating"] = compute_risk_rating(principal)

    return principals


def generate_policy_change_report(
    before_snapshot: list[dict[str, Any]],
    after_snapshot: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate differential report comparing two policy snapshots (FR-019).

    Identifies added, removed, and modified principals along with
    changes in permissions, scores, and risk ratings.

    Args:
        before_snapshot: Earlier catalog snapshot with principals
        after_snapshot: Later catalog snapshot with principals

    Returns:
        Differential report with changes, added, removed principals
    """
    # Build ID->principal maps
    before_map = {p["id"]: p for p in before_snapshot}
    after_map = {p["id"]: p for p in after_snapshot}

    before_ids = set(before_map.keys())
    after_ids = set(after_map.keys())

    # Detect changes
    added = sorted(after_ids - before_ids)
    removed = sorted(before_ids - after_ids)
    potentially_modified = sorted(before_ids & after_ids)

    modifications = []
    for pid in potentially_modified:
        before_principal = before_map[pid]
        after_principal = after_map[pid]

        changes: dict[str, Any] = {"principal_id": pid}

        # Check score changes
        before_score = before_principal.get("least_privilege_score", 100.0)
        after_score = after_principal.get("least_privilege_score", 100.0)
        if abs(before_score - after_score) > 1.0:
            changes["score_change"] = {
                "before": before_score,
                "after": after_score,
                "delta": after_score - before_score,
            }

        # Check risk rating changes
        before_risk = before_principal.get("risk_rating", "LOW")
        after_risk = after_principal.get("risk_rating", "LOW")
        if before_risk != after_risk:
            changes["risk_rating_change"] = {"before": before_risk, "after": after_risk}

        # Check policy summary changes
        before_summary = before_principal.get("policy_summary", {})
        after_summary = after_principal.get("policy_summary", {})
        if isinstance(before_summary, dict) and isinstance(after_summary, dict):
            before_actions = before_summary.get("action_count", 0)
            after_actions = after_summary.get("action_count", 0)
            if before_actions != after_actions:
                changes["action_count_change"] = {
                    "before": before_actions,
                    "after": after_actions,
                    "delta": after_actions - before_actions,
                }

        # Only record if there are actual changes
        if len(changes) > 1:  # More than just principal_id
            modifications.append(changes)

    return {
        "added_principals": [after_map[pid] for pid in added],
        "removed_principals": [before_map[pid] for pid in removed],
        "modified_principals": modifications,
        "summary": {
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modifications),
            "unchanged_count": len(potentially_modified) - len(modifications),
        },
    }


def aggregate_risk_scores(principals: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate enterprise-wide risk metrics from principal data (FR-021).

    Computes overall risk distribution, average scores, and identifies
    high-risk principals requiring attention.

    Args:
        principals: List of enriched principal records

    Returns:
        Aggregated risk metrics with distribution and recommendations
    """
    if not principals:
        return {
            "total_principals": 0,
            "risk_distribution": {"HIGH": 0, "MODERATE": 0, "LOW": 0},
            "average_least_privilege_score": 100.0,
            "high_risk_principals": [],
            "recommendations": [],
        }

    # Risk distribution
    risk_counts = {"HIGH": 0, "MODERATE": 0, "LOW": 0}
    score_sum = 0.0
    high_risk_principals = []

    for principal in principals:
        risk_rating = principal.get("risk_rating", "LOW")
        if risk_rating in risk_counts:
            risk_counts[risk_rating] += 1

        score = principal.get("least_privilege_score", 100.0)
        score_sum += score

        # Collect high-risk details
        if risk_rating == "HIGH":
            high_risk_principals.append(
                {
                    "id": principal["id"],
                    "type": principal.get("type", "unknown"),
                    "risk_rating": risk_rating,
                    "least_privilege_score": score,
                    "inactive": principal.get("inactive", False),
                    "wildcard_actions": (
                        principal.get("policy_summary", {}).get("wildcard_actions", [])
                        if isinstance(principal.get("policy_summary"), dict)
                        else []
                    ),
                }
            )

    average_score = score_sum / len(principals)

    # Generate recommendations
    recommendations = []
    high_risk_pct = (risk_counts["HIGH"] / len(principals)) * 100
    if high_risk_pct > 10:
        recommendations.append(
            f"HIGH risk principals exceed 10% of total ({high_risk_pct:.1f}%). "
            "Review and remediate excessive permissions."
        )

    if average_score < 70:
        recommendations.append(
            f"Average least-privilege score ({average_score:.1f}) below 70. "
            "Consider narrowing permissions and reducing wildcards."
        )

    inactive_high_risk = [p for p in high_risk_principals if p.get("inactive")]
    if inactive_high_risk:
        recommendations.append(
            f"{len(inactive_high_risk)} HIGH risk principals are inactive. "
            "Consider revocation or archival."
        )

    return {
        "total_principals": len(principals),
        "risk_distribution": risk_counts,
        "average_least_privilege_score": round(average_score, 2),
        "high_risk_principals": high_risk_principals,
        "recommendations": recommendations,
    }
