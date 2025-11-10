#!/usr/bin/env python3
"""Governance orchestration script for end-to-end validation runs.

This utility drives the governance package against an AWS environment and
captures artifacts under the reports/ directory. It fetches the principal
catalog, computes risk metrics, exercises authorization/integration/revocation
flows, and generates an evidence pack summary.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REPO_ROOT = Path(__file__).resolve().parents[2]
_GOVERNANCE_SRC = REPO_ROOT / "packages/agentcore-governance/src"


def _import_governance_modules():  # pragma: no cover - simple import shim
    try:
        from agentcore_governance import (
            analyzer as analyzer_module,
        )
        from agentcore_governance import (
            authorization as authorization_module,
        )
        from agentcore_governance import (
            catalog as catalog_module,
        )
        from agentcore_governance import (
            evidence as evidence_module,
        )
        from agentcore_governance import (
            integrations as integrations_module,
        )
        from agentcore_governance import (
            revocation as revocation_module,
        )
    except ModuleNotFoundError:
        sys.path.insert(0, str(_GOVERNANCE_SRC))
        from agentcore_governance import (  # type: ignore[import-not-found]
            analyzer as analyzer_module,
        )
        from agentcore_governance import (
            authorization as authorization_module,
        )
        from agentcore_governance import (
            catalog as catalog_module,
        )
        from agentcore_governance import (
            evidence as evidence_module,
        )
        from agentcore_governance import (
            integrations as integrations_module,
        )
        from agentcore_governance import (
            revocation as revocation_module,
        )

    return (
        analyzer_module,
        authorization_module,
        catalog_module,
        evidence_module,
        integrations_module,
        revocation_module,
    )


analyzer, authorization, catalog, evidence, integrations, revocation = _import_governance_modules()

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


@dataclass
class RunContext:
    environment: str | None
    region: str | None
    profile: str | None
    timestamp: datetime
    output_dir: Path
    integrations_registry: Path
    revocations_registry: Path
    catalog_snapshot_file: Path
    summary_file: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "region": self.region,
            "profile": self.profile,
            "timestamp": self.timestamp.isoformat(),
            "output_dir": str(self.output_dir),
            "artifacts": {
                "catalog_snapshot": str(self.catalog_snapshot_file),
                "integrations_registry": str(self.integrations_registry),
                "revocations_registry": str(self.revocations_registry),
                "summary": str(self.summary_file),
            },
        }


def parse_args() -> argparse.Namespace:
    env_default = os.environ.get("AGENTCORE_ENV")
    region_default = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

    parser = argparse.ArgumentParser(description="Run governance orchestration workflow")
    parser.add_argument(
        "--environment",
        default=env_default,
        help="AgentCore environment name (defaults to $AGENTCORE_ENV)",
    )
    parser.add_argument(
        "--region",
        default=region_default,
        help="AWS region for boto3 session (defaults to $AWS_REGION)",
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="AWS named profile for boto3 session (defaults to $AWS_PROFILE)",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for generated artifacts (default: reports)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format=LOG_FORMAT)


def setup_boto_session(region: str | None, profile: str | None) -> None:
    try:
        boto3.setup_default_session(region_name=region, profile_name=profile)
    except Exception as exc:  # pragma: no cover - boto3 only raises during misconfiguration
        raise RuntimeError(f"Failed to set up boto3 session: {exc}") from exc


def resolve_run_context(args: argparse.Namespace) -> RunContext:
    timestamp = datetime.now(UTC)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    env_label = args.environment or "all"
    integrations_registry = output_dir / f"{env_label}-integrations-registry.json"
    revocations_registry = output_dir / f"{env_label}-revocations-registry.json"
    catalog_snapshot_file = (
        output_dir / f"principal-snapshot-{timestamp.strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_file = (
        output_dir / f"governance-orchestrator-{timestamp.strftime('%Y%m%d-%H%M%S')}.json"
    )

    return RunContext(
        environment=args.environment,
        region=args.region,
        profile=args.profile,
        timestamp=timestamp,
        output_dir=output_dir,
        integrations_registry=integrations_registry,
        revocations_registry=revocations_registry,
        catalog_snapshot_file=catalog_snapshot_file,
        summary_file=summary_file,
    )


def verify_identity() -> dict[str, Any]:
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        logging.info(
            "AWS identity verified: account=%s user=%s",
            identity.get("Account"),
            identity.get("Arn"),
        )
        return identity
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(f"Unable to verify AWS identity: {exc}") from exc


def gather_catalog(context: RunContext) -> dict[str, Any]:
    logging.info("Fetching principal catalog (environment=%s)", context.environment or "all")
    snapshot = catalog.export_catalog_snapshot(
        environment=context.environment, include_metadata=True
    )
    principals = snapshot.get("principals", [])

    logging.info("Enriching %d principals with scores and risk ratings", len(principals))
    analyzer.enrich_principals_with_scores(principals)
    orphans = analyzer.detect_orphan_principals(principals)
    risk_metrics = analyzer.aggregate_risk_scores(principals)

    # Persist snapshot to file for detailed review
    with context.catalog_snapshot_file.open("w", encoding="utf-8") as fp:
        json.dump(snapshot, fp, indent=2)
        logging.info("Catalog snapshot written to %s", context.catalog_snapshot_file)

    return {
        "metadata": snapshot.get("metadata", {}),
        "principal_count": len(principals),
        "inactive_count": sum(1 for p in principals if p.get("inactive")),
        "orphan_count": len(orphans),
        "high_risk_principals": risk_metrics.get("high_risk_principals", [])[:10],
        "risk_distribution": risk_metrics.get("risk_distribution", {}),
        "average_least_privilege_score": risk_metrics.get("average_least_privilege_score"),
        "recommendations": risk_metrics.get("recommendations", []),
    }


def exercise_authorization_workflow(agent_id: str) -> dict[str, Any]:
    logging.info("Simulating authorization update for agent %s", agent_id)
    authorization.clear_authorization_store()
    baseline_tools = ["get_product_info", "search_documentation"]
    authorization.set_authorized_tools(agent_id, baseline_tools, reason="Baseline provisioning")

    updated_tools = baseline_tools + ["check_warranty"]
    change_record = authorization.set_authorized_tools(
        agent_id,
        updated_tools,
        reason="Add warranty check for orchestrated validation",
    )
    differential = authorization.generate_differential_report(agent_id)

    return {
        "agent_id": agent_id,
        "change_record": change_record,
        "differential": differential,
    }


def exercise_integration_workflow(context: RunContext, approver: str) -> dict[str, Any]:
    integrations.initialize_registry(context.integrations_registry)

    payload = {
        "name": "warranty-partner",
        "justification": "External ticket enrichment",
        "requestedTargets": ["gateway:web_search", "gateway:check_warranty"],
    }

    integration_id = integrations.request_integration(payload)
    integrations.approve_integration(
        integration_id,
        approved_targets=["gateway:web_search"],
        expiry_days=90,
        approved_by=approver,
    )

    authorized = integrations.check_target_authorized(integration_id, "gateway:web_search")
    unauthorized = integrations.check_target_authorized(integration_id, "gateway:check_warranty")

    return {
        "integration_id": integration_id,
        "registry_file": str(context.integrations_registry),
        "authorized_target_example": authorized,
        "unauthorized_target_example": unauthorized,
        "status": integrations.get_integration(integration_id),
    }


def exercise_revocation_workflow(context: RunContext, initiator: str) -> dict[str, Any]:
    revocation.initialize_registry(context.revocations_registry)

    payload = {
        "subjectType": "user",
        "subjectId": "sample-user@example.com",
        "scope": "user_access",
        "reason": "Suspicious activity detected",
        "initiatedBy": initiator,
    }

    revocation_id = revocation.create_revocation_request(payload)
    revocation.mark_revocation_propagated(revocation_id)
    sla_metrics = revocation.compute_sla_metrics()

    return {
        "revocation_id": revocation_id,
        "registry_file": str(context.revocations_registry),
        "sla_metrics": sla_metrics,
        "record": revocation.get_revocation_status(revocation_id),
    }


def generate_evidence_pack() -> dict[str, Any]:
    logging.info("Generating evidence pack metadata")
    return evidence.build_evidence_pack({"hours_back": 24})


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    try:
        setup_boto_session(args.region, args.profile)
    except RuntimeError as err:
        logging.error("%s", err)
        return 1

    context = resolve_run_context(args)

    try:
        identity = verify_identity()
    except RuntimeError as err:
        logging.error("%s", err)
        return 1

    summary: dict[str, Any] = {
        "run": context.to_dict(),
        "aws_identity": identity,
        "steps": {},
    }

    errors: list[str] = []

    try:
        summary["steps"]["catalog"] = gather_catalog(context)
    except Exception as exc:  # noqa: BLE001 - orchestrator must capture all errors
        logging.exception("Catalog gathering failed")
        errors.append(f"catalog: {exc}")

    try:
        summary["steps"]["authorization"] = exercise_authorization_workflow(
            agent_id="customer-support-agent"
        )
    except Exception as exc:  # noqa: BLE001
        logging.exception("Authorization workflow failed")
        errors.append(f"authorization: {exc}")

    try:
        approver = identity.get("Arn", "unknown")
        summary["steps"]["integration"] = exercise_integration_workflow(context, approver)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Integration workflow failed")
        errors.append(f"integration: {exc}")

    try:
        initiator = identity.get("Arn", "unknown")
        summary["steps"]["revocation"] = exercise_revocation_workflow(context, initiator)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Revocation workflow failed")
        errors.append(f"revocation: {exc}")

    try:
        summary["steps"]["evidence_pack"] = generate_evidence_pack()
    except Exception as exc:  # noqa: BLE001
        logging.exception("Evidence pack generation failed")
        errors.append(f"evidence_pack: {exc}")

    if errors:
        summary["errors"] = errors
        logging.error("Orchestration completed with %d error(s)", len(errors))
    else:
        logging.info("Orchestration completed successfully")

    with context.summary_file.open("w", encoding="utf-8") as fp:
        json.dump(summary, fp, indent=2, default=str)
        logging.info("Summary written to %s", context.summary_file)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
