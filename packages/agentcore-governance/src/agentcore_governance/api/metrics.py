"""CloudWatch metrics emission wrappers for governance endpoints (T086).

Provides decorators and utilities for emitting CloudWatch metrics from
governance API handlers for operational monitoring.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic decorator
F = TypeVar("F", bound=Callable[..., Any])


def emit_metric(
    metric_name: str,
    value: float = 1.0,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
) -> None:
    """Emit a CloudWatch metric (stub for production integration).

    In production, this would use boto3 CloudWatch client to put metrics.
    For now, it logs metrics for observability testing.

    Args:
        metric_name: Metric name (e.g., "governance.decisions.count")
        value: Metric value
        unit: CloudWatch metric unit (Count, Milliseconds, etc.)
        dimensions: Optional metric dimensions
    """
    dimensions_str = ""
    if dimensions:
        dimensions_str = " " + " ".join(f"{k}={v}" for k, v in dimensions.items())

    logger.info(
        f"METRIC: {metric_name}={value} {unit}{dimensions_str}",
        extra={
            "metric_name": metric_name,
            "metric_value": value,
            "metric_unit": unit,
            "metric_dimensions": dimensions,
        },
    )


def track_endpoint_metrics(endpoint_name: str) -> Callable[[F], F]:
    """Decorator to track endpoint call count and latency.

    Args:
        endpoint_name: Name of the endpoint (e.g., "list_decisions")

    Returns:
        Decorated function with metrics emission
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()

            # Track invocation count
            emit_metric(
                "governance.endpoint.invocations",
                value=1.0,
                unit="Count",
                dimensions={"endpoint": endpoint_name},
            )

            try:
                result = func(*args, **kwargs)

                # Track success count
                emit_metric(
                    "governance.endpoint.success",
                    value=1.0,
                    unit="Count",
                    dimensions={"endpoint": endpoint_name},
                )

                # Track latency
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                emit_metric(
                    "governance.endpoint.latency",
                    value=elapsed_ms,
                    unit="Milliseconds",
                    dimensions={"endpoint": endpoint_name},
                )

                return result

            except Exception as e:
                # Track error count
                emit_metric(
                    "governance.endpoint.errors",
                    value=1.0,
                    unit="Count",
                    dimensions={"endpoint": endpoint_name, "error_type": type(e).__name__},
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def track_decision_metrics(effect: str) -> None:
    """Emit decision-specific metrics.

    Args:
        effect: Decision effect (allow or deny)
    """
    emit_metric(
        "governance.decisions.count",
        value=1.0,
        unit="Count",
        dimensions={"effect": effect},
    )

    if effect == "deny":
        emit_metric("governance.decisions.denied", value=1.0, unit="Count")


def track_revocation_sla(elapsed_ms: float, within_sla: bool) -> None:
    """Emit revocation SLA metrics.

    Args:
        elapsed_ms: Revocation propagation time in milliseconds
        within_sla: Whether revocation met SLA target
    """
    emit_metric("governance.revocations.sla_ms", value=elapsed_ms, unit="Milliseconds")

    emit_metric(
        "governance.revocations.sla_compliance",
        value=1.0 if within_sla else 0.0,
        unit="Count",
    )


def track_risk_distribution(risk_counts: dict[str, int], total_principals: int) -> None:
    """Emit risk distribution metrics.

    Args:
        risk_counts: Dictionary of risk_rating -> count
        total_principals: Total number of principals
    """
    for risk_rating, count in risk_counts.items():
        emit_metric(
            "governance.principals.risk_distribution",
            value=count,
            unit="Count",
            dimensions={"risk_rating": risk_rating},
        )

    # Emit high-risk ratio
    high_risk_count = risk_counts.get("HIGH", 0)
    high_risk_ratio = (high_risk_count / total_principals) if total_principals > 0 else 0.0

    emit_metric(
        "governance.principals.high_risk_ratio",
        value=high_risk_ratio,
        unit="None",
    )


def track_conformance_score(score: float, threshold: float) -> None:
    """Emit least-privilege conformance score metrics.

    Args:
        score: Conformance score percentage (0-100)
        threshold: Target conformance threshold
    """
    emit_metric("governance.conformance.score", value=score, unit="None")

    # Emit threshold compliance
    meets_threshold = 1.0 if score >= threshold else 0.0
    emit_metric("governance.conformance.threshold_compliance", value=meets_threshold, unit="Count")


# Example usage in API handlers:
"""
from agentcore_governance.api.metrics import track_endpoint_metrics, track_decision_metrics

@track_endpoint_metrics("list_decisions")
def list_decisions(subject_id: str | None = None, ...) -> dict[str, Any]:
    # ... implementation ...

    # Emit decision-specific metrics
    for decision in decisions:
        track_decision_metrics(decision["effect"])

    return {"decisions": decisions, ...}
"""
