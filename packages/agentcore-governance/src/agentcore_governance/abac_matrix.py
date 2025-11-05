"""ABAC feasibility matrix exporter."""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable, Mapping
from typing import Any

logger = logging.getLogger(__name__)


def export_abac_matrix(records: Iterable[Mapping[str, str]]) -> dict[str, Any]:
    """Return a serializable representation of the ABAC feasibility matrix.

    Args:
        records: Attribute records with keys: attribute, source, potential_use, collection_method

    Returns:
        Dictionary with 'attributes' list and optional 'csv' export
    """
    attributes = list(records)

    logger.info(f"Exported ABAC matrix with {len(attributes)} attributes")

    return {
        "attributes": attributes,
        "csv_export": _generate_csv_export(attributes),
    }


def _generate_csv_export(attributes: list[Mapping[str, str]]) -> str:
    """Generate CSV representation of attributes.

    Args:
        attributes: List of attribute records

    Returns:
        CSV string
    """
    if not attributes:
        return ""

    output = io.StringIO()
    fieldnames = ["attribute", "source", "potential_use", "collection_method"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)

    writer.writeheader()
    for attr in attributes:
        writer.writerow(
            {
                "attribute": attr.get("attribute", ""),
                "source": attr.get("source", ""),
                "potential_use": attr.get("potential_use", ""),
                "collection_method": attr.get("collection_method", ""),
            }
        )

    return output.getvalue()


def generate_default_abac_matrix() -> dict[str, Any]:
    """Generate default ABAC feasibility matrix based on data model.

    Returns:
        Matrix with standard attributes from the governance data model
    """
    default_attributes = [
        {
            "attribute": "environment",
            "source": "tags/SSM path",
            "potential_use": "Scope decisions by dev/staging/prod",
            "collection_method": "Parse ARN/SSM hierarchy",
        },
        {
            "attribute": "sensitivity_level",
            "source": "tool registry",
            "potential_use": "Conditional access for sensitive tools",
            "collection_method": "Read YAML registry",
        },
        {
            "attribute": "owner",
            "source": "IAM tags",
            "potential_use": "Ownership-based enforcement",
            "collection_method": "IAM listing API",
        },
        {
            "attribute": "risk_rating",
            "source": "analyzer output",
            "potential_use": "Elevated review for high-risk principals",
            "collection_method": "Computed score classification",
        },
        {
            "attribute": "last_used_at",
            "source": "CloudWatch logs",
            "potential_use": "Deactivation triggers for unused resources",
            "collection_method": "Log query aggregation",
        },
    ]

    return export_abac_matrix(default_attributes)
