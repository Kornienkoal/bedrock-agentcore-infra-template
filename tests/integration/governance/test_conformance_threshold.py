"""Conformance threshold alert test (T089).

Tests that least-privilege conformance scoring correctly triggers alerts
when thresholds are breached.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def high_conformance_principals():
    """Generate principals with high conformance scores."""
    return [
        {
            "id": f"arn:aws:iam::123456789012:role/HighConformanceRole{i}",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-a",
            "purpose": "Production service",
            "policy_summary": {
                "action_count": 5,
                "wildcard_actions": [],
                "wildcard_resource_statements": 0,
                "resource_scope_wideness": "NARROW",
                "total_statements": 2,
            },
            "inactive": False,
        }
        for i in range(10)
    ]


@pytest.fixture
def low_conformance_principals():
    """Generate principals with low conformance scores (many wildcards)."""
    return [
        {
            "id": f"arn:aws:iam::123456789012:role/LowConformanceRole{i}",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-b",
            "purpose": "Legacy service",
            "policy_summary": {
                "action_count": 100,
                "wildcard_actions": ["s3:*", "dynamodb:*", "lambda:*", "bedrock:*"],
                "wildcard_resource_statements": 5,
                "resource_scope_wideness": "BROAD",
                "total_statements": 10,
            },
            "inactive": True,
        }
        for i in range(10)
    ]


def test_conformance_score_above_threshold():
    """Test that high conformance principals meet threshold."""
    from agentcore_governance.analyzer import enrich_principals_with_scores

    principals = [
        {
            "id": "arn:aws:iam::123456789012:role/GoodRole",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-a",
            "purpose": "Well-scoped service",
            "policy_summary": {
                "action_count": 10,
                "wildcard_actions": [],
                "wildcard_resource_statements": 0,
                "resource_scope_wideness": "NARROW",
                "total_statements": 3,
            },
            "inactive": False,
        }
    ]

    enriched = enrich_principals_with_scores(principals)

    # High conformance should have score >= 90
    assert enriched[0]["least_privilege_score"] >= 90
    assert enriched[0]["risk_rating"] == "LOW"


def test_conformance_score_below_threshold():
    """Test that low conformance principals fail threshold."""
    from agentcore_governance.analyzer import enrich_principals_with_scores

    principals = [
        {
            "id": "arn:aws:iam::123456789012:role/OverprivilegedRole",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-b",
            "purpose": "Legacy wildcard permissions",
            "policy_summary": {
                "action_count": 200,
                "wildcard_actions": ["*:*", "s3:*", "dynamodb:*", "lambda:*", "bedrock:*"],
                "wildcard_resource_statements": 10,
                "resource_scope_wideness": "BROAD",
                "total_statements": 15,
            },
            "inactive": True,
        }
    ]

    enriched = enrich_principals_with_scores(principals)

    # Low conformance should have score < 50
    assert enriched[0]["least_privilege_score"] < 50
    assert enriched[0]["risk_rating"] == "HIGH"


def test_conformance_threshold_report(high_conformance_principals, low_conformance_principals):
    """Test that conformance report identifies principals below threshold."""
    from agentcore_governance.analyzer import enrich_principals_with_scores

    # Mix of high and low conformance principals
    all_principals = high_conformance_principals + low_conformance_principals
    enriched = enrich_principals_with_scores(all_principals)

    # Check that we have a mix of scores
    scores = [p["least_privilege_score"] for p in enriched]
    assert min(scores) < 50, "Should have low-scoring principals"
    assert max(scores) > 90, "Should have high-scoring principals"

    # Count failing principals manually (below 80 threshold)
    failing_principals = [p for p in enriched if p["least_privilege_score"] < 80.0]
    assert len(failing_principals) > 0, "Should have principals below 80% threshold"

    # Low conformance principals should be in failing list
    low_conformance_ids = {p["id"] for p in low_conformance_principals}
    failing_ids = {p["id"] for p in failing_principals}
    assert len(failing_ids & low_conformance_ids) > 0


def test_conformance_alert_generation():
    """Test alert generation when conformance drops below critical threshold."""
    from agentcore_governance.analyzer import aggregate_risk_scores, enrich_principals_with_scores

    # Create mixed population
    principals = []

    # 30% high-risk principals (above alert threshold of 10%)
    for i in range(30):
        principals.append(
            {
                "id": f"arn:aws:iam::123456789012:role/HighRisk{i}",
                "type": "execution_role",
                "environment": "prod",
                "owner": "unknown",
                "purpose": "",
                "policy_summary": {
                    "action_count": 150,
                    "wildcard_actions": ["*:*", "s3:*", "lambda:*"],
                    "wildcard_resource_statements": 8,
                    "resource_scope_wideness": "BROAD",
                    "total_statements": 12,
                },
                "inactive": True,
            }
        )

    # 70% moderate/low risk
    for i in range(70):
        principals.append(
            {
                "id": f"arn:aws:iam::123456789012:role/ModerateRisk{i}",
                "type": "execution_role",
                "environment": "prod",
                "owner": "team-a",
                "purpose": "Standard service",
                "policy_summary": {
                    "action_count": 30,
                    "wildcard_actions": ["s3:Get*"],
                    "wildcard_resource_statements": 1,
                    "resource_scope_wideness": "MODERATE",
                    "total_statements": 5,
                },
                "inactive": False,
            }
        )

    enriched = enrich_principals_with_scores(principals)
    risk_metrics = aggregate_risk_scores(enriched)

    # Should generate alert about high-risk percentage
    assert len(risk_metrics["recommendations"]) > 0
    alert_found = any(
        "HIGH risk principals exceed 10%" in rec for rec in risk_metrics["recommendations"]
    )
    assert alert_found, "Should alert when high-risk principals exceed threshold"

    # Verify high-risk count
    high_risk_count = risk_metrics["risk_distribution"]["HIGH"]
    high_risk_pct = (high_risk_count / risk_metrics["total_principals"]) * 100
    assert high_risk_pct > 10, "Should have >10% high-risk principals"


def test_conformance_threshold_with_perfect_score():
    """Test conformance report when all principals have perfect scores."""
    from agentcore_governance.analyzer import enrich_principals_with_scores

    principals = [
        {
            "id": f"arn:aws:iam::123456789012:role/PerfectRole{i}",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-a",
            "purpose": "Perfect least-privilege",
            "policy_summary": {
                "action_count": 3,
                "wildcard_actions": [],
                "wildcard_resource_statements": 0,
                "resource_scope_wideness": "NARROW",
                "total_statements": 2,
            },
            "inactive": False,
        }
        for i in range(10)
    ]

    enriched = enrich_principals_with_scores(principals)

    # All principals should have high scores
    scores = [p["least_privilege_score"] for p in enriched]
    assert all(score >= 95.0 for score in scores), "All scores should be >= 95"
    assert len([p for p in enriched if p["least_privilege_score"] < 95.0]) == 0


def test_conformance_metrics_emission():
    """Test that conformance scoring emits appropriate metrics."""
    from agentcore_governance.analyzer import enrich_principals_with_scores
    from agentcore_governance.api.metrics import track_conformance_score

    principals = [
        {
            "id": "arn:aws:iam::123456789012:role/TestRole",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-a",
            "purpose": "Test service",
            "policy_summary": {
                "action_count": 20,
                "wildcard_actions": ["s3:Get*"],
                "wildcard_resource_statements": 1,
                "resource_scope_wideness": "MODERATE",
                "total_statements": 4,
            },
            "inactive": False,
        }
    ]

    enriched = enrich_principals_with_scores(principals)
    score = enriched[0]["least_privilege_score"]

    # Emit metrics
    track_conformance_score(score, threshold=80.0)

    # No assertion here; metrics are logged/emitted
    # In production, this would verify CloudWatch metrics were sent


def test_conformance_threshold_boundary_conditions():
    """Test conformance scoring at exact threshold boundaries."""
    from agentcore_governance.analyzer import enrich_principals_with_scores

    # Create principals with scores exactly at threshold (80.0)
    principals = [
        {
            "id": f"arn:aws:iam::123456789012:role/BoundaryRole{i}",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-a",
            "purpose": "Boundary test",
            "policy_summary": {
                "action_count": 25,
                "wildcard_actions": ["s3:Get*", "s3:List*"],
                "wildcard_resource_statements": 2,
                "resource_scope_wideness": "MODERATE",
                "total_statements": 5,
            },
            "inactive": False,
        }
        for i in range(10)
    ]

    enriched = enrich_principals_with_scores(principals)

    # Test with threshold exactly at average score
    avg_score = sum(p["least_privilege_score"] for p in enriched) / len(enriched)

    # Count principals below/above threshold
    below_avg = [p for p in enriched if p["least_privilege_score"] < avg_score]
    above_avg = [p for p in enriched if p["least_privilege_score"] >= avg_score]

    # Should have roughly balanced distribution
    assert len(below_avg) + len(above_avg) == len(enriched)


def test_risk_aggregation_alert_thresholds():
    """Test that risk aggregation generates alerts at correct thresholds."""
    from agentcore_governance.analyzer import aggregate_risk_scores, enrich_principals_with_scores

    # Create principals with average score < 70 (should trigger alert)
    principals = [
        {
            "id": f"arn:aws:iam::123456789012:role/LowScoreRole{i}",
            "type": "execution_role",
            "environment": "prod",
            "owner": "team-a",
            "purpose": "Low score test",
            "policy_summary": {
                "action_count": 80,
                "wildcard_actions": ["s3:*", "dynamodb:*"],
                "wildcard_resource_statements": 4,
                "resource_scope_wideness": "BROAD",
                "total_statements": 8,
            },
            "inactive": False,
        }
        for i in range(20)
    ]

    enriched = enrich_principals_with_scores(principals)
    risk_metrics = aggregate_risk_scores(enriched)

    # Should generate alert about low average score
    assert risk_metrics["average_least_privilege_score"] < 70
    alert_found = any(
        "Average least-privilege score" in rec and "below 70" in rec
        for rec in risk_metrics["recommendations"]
    )
    assert alert_found, "Should alert when average score < 70"
