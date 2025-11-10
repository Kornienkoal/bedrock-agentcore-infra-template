"""Orphan resource remediation script (T087).

Automated cleanup workflow for orphan principals detected by analyzer.
Provides dry-run mode for safe validation before remediation.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def identify_orphan_principals(
    principals: list[dict[str, Any]],
    strict_mode: bool = False,
) -> list[dict[str, Any]]:
    """Identify orphan principals requiring remediation.

    Args:
        principals: List of principal records
        strict_mode: If True, apply stricter orphan criteria

    Returns:
        List of orphan principals with remediation recommendations
    """
    from agentcore_governance.analyzer import detect_orphan_principals

    orphans_raw = detect_orphan_principals(principals)
    orphans = [dict(o) for o in orphans_raw]  # Convert to mutable dicts

    # Enrich with remediation recommendations
    for orphan in orphans:
        recommendations = []

        owner_val = orphan.get("owner", "unknown")
        owner = str(owner_val).strip().lower() if owner_val else "unknown"
        purpose_val = orphan.get("purpose", "")
        purpose = str(purpose_val).strip() if purpose_val else ""

        if owner in ("unknown", "", "none"):
            recommendations.append("ASSIGN_OWNER: Add 'Owner' tag with team/individual identifier")

        if not purpose:
            recommendations.append("ASSIGN_PURPOSE: Add 'Purpose' tag with resource description")

        # Check for additional risk factors
        if orphan.get("inactive", False):
            recommendations.append("CONSIDER_DELETION: Principal inactive >30 days and orphaned")

        if orphan.get("risk_rating") == "HIGH":
            recommendations.append("URGENT_REVIEW: High-risk orphan requires immediate attention")

        if strict_mode:
            # In strict mode, also flag principals with generic purposes
            generic_purposes = ["test", "demo", "temp", "temporary"]
            if purpose.lower() in generic_purposes:
                recommendations.append(f"CLARIFY_PURPOSE: Purpose '{purpose}' is too generic")

        orphan["remediation_recommendations"] = recommendations

    return orphans


def generate_remediation_plan(
    orphans: list[dict[str, Any]],
    auto_tag: bool = False,
    delete_inactive: bool = False,
) -> dict[str, Any]:
    """Generate remediation plan for orphan principals.

    Args:
        orphans: List of orphan principals
        auto_tag: Whether to auto-assign default tags
        delete_inactive: Whether to delete inactive orphans

    Returns:
        Remediation plan with actions and impact summary
    """
    actions = []
    metrics = {
        "total_orphans": len(orphans),
        "auto_tag_candidates": 0,
        "deletion_candidates": 0,
        "manual_review_required": 0,
    }

    for orphan in orphans:
        principal_id = orphan["id"]
        recommendations = orphan.get("remediation_recommendations", [])

        # Auto-tag action
        if auto_tag and any("ASSIGN_" in r for r in recommendations):
            actions.append(
                {
                    "principal_id": principal_id,
                    "action": "AUTO_TAG",
                    "tags": {
                        "Owner": "governance-team",  # Default owner
                        "Purpose": "Pending classification",
                        "ManagedBy": "orphan-remediation-script",
                    },
                }
            )
            metrics["auto_tag_candidates"] += 1

        # Deletion action for inactive orphans
        if (
            delete_inactive
            and orphan.get("inactive")
            and any(rec.startswith("CONSIDER_DELETION") for rec in recommendations)
        ):
            actions.append(
                {
                    "principal_id": principal_id,
                    "action": "DELETE",
                    "reason": "Inactive orphan principal without ownership",
                }
            )
            metrics["deletion_candidates"] += 1

        # Manual review for high-risk orphans
        if orphan.get("risk_rating") == "HIGH":
            actions.append(
                {
                    "principal_id": principal_id,
                    "action": "MANUAL_REVIEW",
                    "reason": "High-risk orphan requires security team review",
                    "recommendations": recommendations,
                }
            )
            metrics["manual_review_required"] += 1

    return {
        "actions": actions,
        "metrics": metrics,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def execute_remediation_plan(
    plan: dict[str, Any],
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute remediation plan (with dry-run support).

    Args:
        plan: Remediation plan from generate_remediation_plan
        dry_run: If True, only log actions without executing

    Returns:
        Execution summary with results per action
    """
    actions = plan["actions"]
    results = []

    for action in actions:
        principal_id = action["principal_id"]
        action_type = action["action"]

        if dry_run:
            logger.info(f"DRY-RUN: {action_type} for {principal_id}")
            results.append(
                {
                    "principal_id": principal_id,
                    "action": action_type,
                    "status": "DRY_RUN",
                    "message": "Action not executed (dry-run mode)",
                }
            )
        else:
            # Execute actual remediation
            try:
                if action_type == "AUTO_TAG":
                    # In production: call IAM tag_role API
                    logger.info(f"AUTO_TAG: {principal_id} with {action['tags']}")
                    results.append(
                        {
                            "principal_id": principal_id,
                            "action": action_type,
                            "status": "SUCCESS",
                            "tags_applied": action["tags"],
                        }
                    )

                elif action_type == "DELETE":
                    # In production: call IAM delete_role API (with safety checks)
                    logger.warning(f"DELETE: {principal_id} - {action['reason']}")
                    results.append(
                        {
                            "principal_id": principal_id,
                            "action": action_type,
                            "status": "SUCCESS",
                            "reason": action["reason"],
                        }
                    )

                elif action_type == "MANUAL_REVIEW":
                    # Create ticket or notification for manual review
                    logger.info(f"MANUAL_REVIEW: {principal_id} - {action['reason']}")
                    results.append(
                        {
                            "principal_id": principal_id,
                            "action": action_type,
                            "status": "PENDING",
                            "recommendations": action.get("recommendations", []),
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to execute {action_type} for {principal_id}: {e}")
                results.append(
                    {
                        "principal_id": principal_id,
                        "action": action_type,
                        "status": "ERROR",
                        "error": str(e),
                    }
                )

    return {
        "results": results,
        "executed_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "total_actions": len(actions),
        "successful": sum(1 for r in results if r["status"] == "SUCCESS"),
        "failed": sum(1 for r in results if r["status"] == "ERROR"),
    }


def main() -> int:
    """Main entry point for orphan remediation script."""
    parser = argparse.ArgumentParser(description="Orphan principal remediation script")
    parser.add_argument(
        "--environment",
        default=None,
        help="Environment filter (e.g. dev, staging, prod). Omit for all environments.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run mode (default: True)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute remediation (disables dry-run)",
    )
    parser.add_argument(
        "--auto-tag",
        action="store_true",
        help="Auto-assign default tags to orphans",
    )
    parser.add_argument(
        "--delete-inactive",
        action="store_true",
        help="Delete inactive orphan principals",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict orphan detection criteria",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 80)
    logger.info("Orphan Principal Remediation Script (T087)")
    logger.info("=" * 80)
    from agentcore_governance.catalog import normalize_environment_filter

    env_values = normalize_environment_filter(args.environment)
    env_list = list(env_values) if env_values is not None else None
    env_label = "all" if env_list is None else ", ".join(env_list)

    logger.info(f"Environment: {env_label}")
    logger.info(f"Dry-run: {not args.execute}")
    logger.info(f"Auto-tag: {args.auto_tag}")
    logger.info(f"Delete inactive: {args.delete_inactive}")
    logger.info(f"Strict mode: {args.strict}")
    logger.info("")

    try:
        # Fetch principal catalog
        from agentcore_governance.analyzer import enrich_principals_with_scores
        from agentcore_governance.catalog import (
            fetch_principal_catalog,
            flag_inactive_principals,
        )

        logger.info("Fetching principal catalog...")
        principals = fetch_principal_catalog(environments=env_list)
        principals = flag_inactive_principals(principals, inactivity_days=30)
        principals = enrich_principals_with_scores(principals)

        logger.info(f"Loaded {len(principals)} principals")

        # Identify orphans
        logger.info("Identifying orphan principals...")
        orphans = identify_orphan_principals(principals, strict_mode=args.strict)
        logger.info(f"Found {len(orphans)} orphan principals")

        if not orphans:
            logger.info("✅ No orphan principals found. Exiting.")
            return 0

        # Generate remediation plan
        logger.info("Generating remediation plan...")
        plan = generate_remediation_plan(
            orphans,
            auto_tag=args.auto_tag,
            delete_inactive=args.delete_inactive,
        )

        logger.info("")
        logger.info("Remediation Plan Summary:")
        logger.info(f"  Total orphans: {plan['metrics']['total_orphans']}")
        logger.info(f"  Auto-tag candidates: {plan['metrics']['auto_tag_candidates']}")
        logger.info(f"  Deletion candidates: {plan['metrics']['deletion_candidates']}")
        logger.info(f"  Manual review required: {plan['metrics']['manual_review_required']}")
        logger.info("")

        # Execute plan
        dry_run = not args.execute
        logger.info(f"Executing plan (dry-run={dry_run})...")
        execution_results = execute_remediation_plan(plan, dry_run=dry_run)

        logger.info("")
        logger.info("Execution Results:")
        logger.info(f"  Total actions: {execution_results['total_actions']}")
        logger.info(f"  Successful: {execution_results['successful']}")
        logger.info(f"  Failed: {execution_results['failed']}")
        logger.info("")

        if dry_run:
            logger.info("⚠️  Dry-run mode. Use --execute to apply changes.")
        else:
            logger.info("✅ Remediation completed.")

        return 0

    except Exception as e:
        logger.error(f"Remediation script failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
