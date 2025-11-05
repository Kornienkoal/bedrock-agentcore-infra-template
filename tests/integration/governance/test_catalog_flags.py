"""Integration tests for inactivity and risk flagging."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from agentcore_governance import analyzer, catalog


class TestInactivityFlagging:
    """Integration tests for inactivity flagging logic."""

    def test_flag_recently_used_principal(self):
        """Test that recently used principals are not flagged as inactive."""
        recent_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        principals = [
            {"id": "role-1", "last_used_at": recent_date},
        ]

        result = catalog.flag_inactive_principals(principals, inactivity_days=30)

        assert result[0]["inactive"] is False

    def test_flag_old_principal(self):
        """Test that old principals are flagged as inactive."""
        old_date = (datetime.now(UTC) - timedelta(days=45)).isoformat()
        principals = [
            {"id": "role-1", "last_used_at": old_date},
        ]

        result = catalog.flag_inactive_principals(principals, inactivity_days=30)

        assert result[0]["inactive"] is True

    def test_flag_principal_never_used(self):
        """Test that principals without last_used_at are flagged as inactive."""
        principals = [
            {"id": "role-1"},
        ]

        result = catalog.flag_inactive_principals(principals, inactivity_days=30)

        assert result[0]["inactive"] is True

    def test_flag_principal_invalid_date(self):
        """Test that principals with invalid dates are flagged as inactive."""
        principals = [
            {"id": "role-1", "last_used_at": "invalid-date"},
        ]

        result = catalog.flag_inactive_principals(principals, inactivity_days=30)

        assert result[0]["inactive"] is True

    def test_custom_inactivity_threshold(self):
        """Test custom inactivity threshold."""
        date_20_days = (datetime.now(UTC) - timedelta(days=20)).isoformat()
        date_50_days = (datetime.now(UTC) - timedelta(days=50)).isoformat()

        principals = [
            {"id": "role-1", "last_used_at": date_20_days},
            {"id": "role-2", "last_used_at": date_50_days},
        ]

        result = catalog.flag_inactive_principals(principals, inactivity_days=40)

        assert result[0]["inactive"] is False
        assert result[1]["inactive"] is True


class TestRiskRatingComputation:
    """Integration tests for risk rating computation."""

    def test_low_risk_principal(self):
        """Test principal with low risk profile."""
        principal = {
            "id": "role-safe",
            "policy_summary": {
                "wildcard_actions": [],
                "resource_scope_wideness": "NARROW",
                "action_count": 10,
            },
            "inactive": False,
            "least_privilege_score": 95.0,
        }

        rating = analyzer.compute_risk_rating(principal)

        assert rating == "LOW"

    def test_high_risk_principal(self):
        """Test principal with high risk profile."""
        principal = {
            "id": "role-dangerous",
            "policy_summary": {
                "wildcard_actions": ["s3:*", "dynamodb:*", "lambda:*", "ec2:*", "iam:*", "rds:*"],
                "resource_scope_wideness": "BROAD",
                "action_count": 150,
            },
            "inactive": True,
            "least_privilege_score": 30.0,
        }

        rating = analyzer.compute_risk_rating(principal)

        assert rating == "HIGH"

    def test_moderate_risk_principal(self):
        """Test principal with moderate risk profile."""
        principal = {
            "id": "role-medium",
            "policy_summary": {
                "wildcard_actions": ["s3:*", "dynamodb:*"],
                "resource_scope_wideness": "MODERATE",
                "action_count": 60,
            },
            "inactive": False,
            "least_privilege_score": 70.0,
        }

        rating = analyzer.compute_risk_rating(principal)

        assert rating == "MODERATE"

    def test_risk_rating_with_missing_fields(self):
        """Test risk rating computation handles missing fields gracefully."""
        principal = {"id": "role-minimal"}

        rating = analyzer.compute_risk_rating(principal)

        assert rating in ("LOW", "MODERATE", "HIGH")

    def test_inactive_increases_risk(self):
        """Test that inactivity increases risk rating."""
        base_principal = {
            "wildcard_actions": [],
            "resource_scope_wideness": "NARROW",
            "least_privilege_score": 85.0,
        }

        active_principal = {**base_principal, "inactive": False}
        inactive_principal = {**base_principal, "inactive": True}

        active_rating = analyzer.compute_risk_rating(active_principal)
        inactive_rating = analyzer.compute_risk_rating(inactive_principal)

        # Inactive should have same or higher risk
        risk_order = ["LOW", "MODERATE", "HIGH"]
        assert risk_order.index(inactive_rating) >= risk_order.index(active_rating)


class TestCatalogWithFlagsIntegration:
    """End-to-end integration tests for catalog with flags."""

    def test_full_workflow_with_mock_principals(self):
        """Test complete workflow: fetch mock principals → flag inactivity → compute risk."""
        # Create mock principals directly (skip AWS mocking complexity)
        mock_principals = [
            {
                "id": "arn:aws:iam::123456789012:role/test-role-active",
                "type": "execution_role",
                "environment": "dev",
                "owner": "team-x",
                "purpose": "Testing",
                "last_used_at": (datetime.now(UTC) - timedelta(days=5)).isoformat(),
                "policy_summary": {
                    "wildcard_actions": [],
                    "resource_scope_wideness": "NARROW",
                    "least_privilege_score": 95.0,
                },
            },
            {
                "id": "arn:aws:iam::123456789012:role/test-role-inactive",
                "type": "execution_role",
                "environment": "dev",
                "owner": "unknown",
                "purpose": "",
                "last_used_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
                "policy_summary": {
                    "wildcard_actions": ["s3:*", "dynamodb:*"],
                    "resource_scope_wideness": "BROAD",
                    "least_privilege_score": 40.0,
                },
            },
        ]

        # Apply inactivity flagging
        principals = catalog.flag_inactive_principals(mock_principals.copy())

        # Compute risk ratings
        for principal in principals:
            policy_summary = principal.get("policy_summary", {})
            principal["wildcard_actions"] = policy_summary.get("wildcard_actions", [])
            principal["resource_scope_wideness"] = policy_summary.get(
                "resource_scope_wideness", "NARROW"
            )
            principal["least_privilege_score"] = policy_summary.get("least_privilege_score", 100.0)
            principal["risk_rating"] = analyzer.compute_risk_rating(principal)

        assert len(principals) == 2

        # Active principal
        active = principals[0]
        assert active["inactive"] is False
        assert active["risk_rating"] == "LOW"

        # Inactive principal
        inactive = principals[1]
        assert inactive["inactive"] is True
        assert inactive["risk_rating"] in ("MODERATE", "HIGH")  # Should have higher risk

    def test_export_snapshot_structure(self):
        """Test that exported snapshot has correct structure."""
        mock_principals = [
            {
                "id": "test-role",
                "owner": "team",
                "last_used_at": (datetime.now(UTC) - timedelta(days=45)).isoformat(),
            }
        ]

        with patch(
            "agentcore_governance.catalog.fetch_principal_catalog", return_value=mock_principals
        ):
            snapshot = catalog.export_catalog_snapshot(environment="dev")

        assert "principals" in snapshot
        assert "metadata" in snapshot
        assert "timestamp" in snapshot["metadata"]
        assert "environment" in snapshot["metadata"]
        assert "total_count" in snapshot["metadata"]
        assert "inactive_count" in snapshot["metadata"]
        assert snapshot["metadata"]["total_count"] == 1
        assert snapshot["metadata"]["inactive_count"] == 1
        assert snapshot["principals"][0]["inactive"] is True
