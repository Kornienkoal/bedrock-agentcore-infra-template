"""Contract tests for /catalog/principals endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agentcore_governance.api import catalog_handlers


class TestGetPrincipalsEndpoint:
    """Contract tests for GET /catalog/principals endpoint."""

    def test_response_schema_basic(self):
        """Test that response contains required top-level fields."""
        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=[]):
            response = catalog_handlers.get_principals()

        assert "principals" in response
        assert "pagination" in response
        assert "filters" in response
        assert isinstance(response["principals"], list)
        assert isinstance(response["pagination"], dict)
        assert isinstance(response["filters"], dict)

    def test_pagination_metadata_schema(self):
        """Test pagination metadata structure."""
        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=[]):
            response = catalog_handlers.get_principals()

        pagination = response["pagination"]
        assert "page" in pagination
        assert "page_size" in pagination
        assert "total_items" in pagination
        assert "total_pages" in pagination
        assert "has_next" in pagination
        assert "has_prev" in pagination

    def test_principal_schema_fields(self):
        """Test that principal objects have required fields."""
        mock_principals = [
            {
                "id": "arn:aws:iam::123456789012:role/test-role",
                "type": "execution_role",
                "environment": "dev",
                "namespace": "test",
                "owner": "team-x",
                "purpose": "Test role",
                "created_at": "2024-01-01T00:00:00Z",
                "last_used_at": "2024-11-01T00:00:00Z",
                "tags": {},
                "status": "active",
                "policy_summary": {
                    "action_count": 5,
                    "wildcard_actions": [],
                    "resource_scope_wideness": "NARROW",
                    "least_privilege_score": 95.0,
                },
            }
        ]

        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=mock_principals):
            response = catalog_handlers.get_principals()

        principals = response["principals"]
        assert len(principals) == 1

        principal = principals[0]
        # Required fields from data model
        assert "id" in principal
        assert "type" in principal
        assert "environment" in principal
        assert "owner" in principal
        assert "purpose" in principal
        # Computed fields
        assert "inactive" in principal
        assert "risk_rating" in principal
        assert principal["risk_rating"] in ("LOW", "MODERATE", "HIGH")

    def test_environment_filter_applied(self):
        """Test that environment filter is reflected in response."""
        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=[]):
            response = catalog_handlers.get_principals(environment="prod")

        assert response["filters"]["environment"] == "prod"

    def test_owner_filter_applied(self):
        """Test that owner filter is reflected in response."""
        mock_principals = [
            {"id": "role-1", "owner": "team-a", "last_used_at": "2024-11-01T00:00:00Z"},
            {"id": "role-2", "owner": "team-b", "last_used_at": "2024-11-01T00:00:00Z"},
        ]

        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=mock_principals):
            response = catalog_handlers.get_principals(owner="team-a")

        assert response["filters"]["owner"] == "team-a"
        assert len(response["principals"]) == 1
        assert response["principals"][0]["owner"] == "team-a"

    def test_pagination_page_boundaries(self):
        """Test pagination with multiple pages."""
        mock_principals = [{"id": f"role-{i}", "owner": "team", "last_used_at": "2024-11-01T00:00:00Z"} for i in range(150)]

        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=mock_principals):
            # Page 1
            response_p1 = catalog_handlers.get_principals(page=1, page_size=100)
            assert response_p1["pagination"]["page"] == 1
            assert response_p1["pagination"]["total_pages"] == 2
            assert response_p1["pagination"]["has_next"] is True
            assert response_p1["pagination"]["has_prev"] is False
            assert len(response_p1["principals"]) == 100

            # Page 2
            response_p2 = catalog_handlers.get_principals(page=2, page_size=100)
            assert response_p2["pagination"]["page"] == 2
            assert response_p2["pagination"]["has_next"] is False
            assert response_p2["pagination"]["has_prev"] is True
            assert len(response_p2["principals"]) == 50

    def test_ownership_validation_fallback(self):
        """Test that ownership validation adds fallback labels."""
        mock_principals = [
            {"id": "role-1", "owner": "", "purpose": "", "last_used_at": "2024-11-01T00:00:00Z"},
            {"id": "role-2", "owner": "unknown", "purpose": "Valid purpose", "last_used_at": "2024-11-01T00:00:00Z"},
        ]

        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=mock_principals):
            response = catalog_handlers.get_principals()

        principals = response["principals"]
        assert principals[0]["owner"] == "UNASSIGNED"
        assert principals[0]["ownership_status"] == "missing"
        assert principals[0]["purpose"] == "No purpose documented"
        assert principals[0]["purpose_status"] == "missing"

        assert principals[1]["owner"] == "UNASSIGNED"
        assert principals[1]["ownership_status"] == "missing"
        assert principals[1]["purpose_status"] == "documented"

    def test_error_handling(self):
        """Test error handling returns proper error structure."""
        with patch("agentcore_governance.catalog.fetch_principal_catalog", side_effect=Exception("Test error")):
            response = catalog_handlers.get_principals()

        assert "error" in response
        assert response["error"] == "Test error"
        assert response["principals"] == []
        assert response["pagination"]["total_items"] == 0

    def test_risk_rating_computed(self):
        """Test that risk ratings are computed for all principals."""
        mock_principals = [
            {
                "id": "role-high-risk",
                "owner": "team",
                "last_used_at": "2023-01-01T00:00:00Z",  # Very old
                "policy_summary": {
                    "wildcard_actions": ["s3:*", "dynamodb:*", "lambda:*", "ec2:*", "iam:*", "rds:*"],
                    "resource_scope_wideness": "BROAD",
                    "least_privilege_score": 30.0,
                },
            },
            {
                "id": "role-low-risk",
                "owner": "team",
                "last_used_at": "2024-11-04T00:00:00Z",  # Recent
                "policy_summary": {
                    "wildcard_actions": [],
                    "resource_scope_wideness": "NARROW",
                    "least_privilege_score": 95.0,
                },
            },
        ]

        with patch("agentcore_governance.catalog.fetch_principal_catalog", return_value=mock_principals):
            response = catalog_handlers.get_principals()

        principals = response["principals"]
        assert principals[0]["risk_rating"] == "HIGH"
        assert principals[1]["risk_rating"] == "LOW"
