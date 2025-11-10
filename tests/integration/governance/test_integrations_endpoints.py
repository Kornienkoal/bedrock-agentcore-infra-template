"""Contract tests for integration management endpoints."""

from __future__ import annotations

import uuid

import pytest
from agentcore_governance import integrations
from agentcore_governance.api import integration_handlers


@pytest.fixture(autouse=True)
def reset_integration_registry():
    """Reset integration registry before each test."""
    integrations._integrations_registry.clear()
    yield
    integrations._integrations_registry.clear()


class TestIntegrationRequestEndpoint:
    """Test POST /integrations endpoint contract."""

    def test_successful_integration_request(self):
        """Test successful integration request with all required fields."""
        payload = {
            "name": "external-api-integration",
            "justification": "Required for customer data enrichment",
            "requestedTargets": [
                "https://api.external.com/v1/customers",
                "https://api.external.com/v1/orders",
            ],
        }

        response = integration_handlers.handle_integration_request(payload)

        # Verify response structure
        assert "integration_id" in response
        assert "status" in response
        assert "correlation_id" in response
        assert response["status"] == "pending"

        # Verify integration was created
        integration = integrations.get_integration(response["integration_id"])
        assert integration is not None
        assert integration["name"] == "external-api-integration"
        assert integration["status"] == "pending"
        assert len(integration["requested_targets"]) == 2

    def test_missing_required_field_name(self):
        """Test request fails when name is missing."""
        payload = {
            "justification": "Some reason",
            "requestedTargets": ["https://api.example.com"],
        }

        with pytest.raises(ValueError, match="Missing required field: name"):
            integration_handlers.handle_integration_request(payload)

    def test_missing_required_field_justification(self):
        """Test request fails when justification is missing."""
        payload = {
            "name": "test-integration",
            "requestedTargets": ["https://api.example.com"],
        }

        with pytest.raises(ValueError, match="Missing required field: justification"):
            integration_handlers.handle_integration_request(payload)

    def test_missing_required_field_requested_targets(self):
        """Test request fails when requestedTargets is missing."""
        payload = {
            "name": "test-integration",
            "justification": "Some reason",
        }

        with pytest.raises(ValueError, match="Missing required field: requestedTargets"):
            integration_handlers.handle_integration_request(payload)

    def test_requested_targets_not_a_list(self):
        """Test request fails when requestedTargets is not a list."""
        payload = {
            "name": "test-integration",
            "justification": "Some reason",
            "requestedTargets": "not-a-list",
        }

        with pytest.raises(ValueError, match="requestedTargets must be a list"):
            integration_handlers.handle_integration_request(payload)

    def test_requested_targets_empty_list(self):
        """Test request fails when requestedTargets is empty."""
        payload = {
            "name": "test-integration",
            "justification": "Some reason",
            "requestedTargets": [],
        }

        with pytest.raises(ValueError, match="requestedTargets cannot be empty"):
            integration_handlers.handle_integration_request(payload)


class TestIntegrationApprovalEndpoint:
    """Test POST /integrations/{integrationId}/approve endpoint contract."""

    def test_successful_integration_approval(self):
        """Test successful integration approval."""
        # Create a pending integration first
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing approval",
                "requestedTargets": [
                    "https://api.example.com/endpoint1",
                    "https://api.example.com/endpoint2",
                ],
            }
        )

        # Approve with subset of targets
        payload = {
            "approvedTargets": ["https://api.example.com/endpoint1"],
            "expiryDays": 90,
        }

        response = integration_handlers.handle_integration_approval(
            integration_id=integration_id,
            payload=payload,
            approved_by="admin@example.com",
        )

        # Verify response structure
        assert response["integration_id"] == integration_id
        assert response["status"] == "active"
        assert response["approved_targets"] == ["https://api.example.com/endpoint1"]
        assert response["approved_by"] == "admin@example.com"
        assert "expires_at" in response
        assert "correlation_id" in response

        # Verify integration was updated
        integration = integrations.get_integration(integration_id)
        assert integration["status"] == "active"
        assert integration["approved_by"] == "admin@example.com"

    def test_approval_without_expiry(self):
        """Test approval without expiry date."""
        integration_id = integrations.request_integration(
            {
                "name": "permanent-integration",
                "justification": "Long-term integration",
                "requestedTargets": ["https://api.example.com/endpoint"],
            }
        )

        payload = {
            "approvedTargets": ["https://api.example.com/endpoint"],
        }

        response = integration_handlers.handle_integration_approval(
            integration_id=integration_id,
            payload=payload,
            approved_by="admin@example.com",
        )

        assert response["expires_at"] is None

    def test_approval_integration_not_found(self):
        """Test approval fails when integration doesn't exist."""
        fake_id = uuid.uuid4().hex
        payload = {
            "approvedTargets": ["https://api.example.com/endpoint"],
        }

        with pytest.raises(ValueError, match=f"Integration not found: {fake_id}"):
            integration_handlers.handle_integration_approval(
                integration_id=fake_id,
                payload=payload,
                approved_by="admin@example.com",
            )

    def test_approval_missing_approved_targets(self):
        """Test approval fails when approvedTargets is missing."""
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing",
                "requestedTargets": ["https://api.example.com/endpoint"],
            }
        )

        payload = {"expiryDays": 90}

        with pytest.raises(ValueError, match="Missing required field: approvedTargets"):
            integration_handlers.handle_integration_approval(
                integration_id=integration_id,
                payload=payload,
                approved_by="admin@example.com",
            )

    def test_approval_invalid_expiry_days(self):
        """Test approval fails with negative expiry days."""
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing",
                "requestedTargets": ["https://api.example.com/endpoint"],
            }
        )

        payload = {
            "approvedTargets": ["https://api.example.com/endpoint"],
            "expiryDays": -10,
        }

        with pytest.raises(ValueError, match="expiryDays must be a positive integer"):
            integration_handlers.handle_integration_approval(
                integration_id=integration_id,
                payload=payload,
                approved_by="admin@example.com",
            )

    def test_approval_already_approved_integration(self):
        """Test approval fails when integration is not in pending status."""
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing",
                "requestedTargets": ["https://api.example.com/endpoint"],
            }
        )

        # First approval
        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/endpoint"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Second approval attempt
        payload = {
            "approvedTargets": ["https://api.example.com/endpoint"],
        }

        with pytest.raises(ValueError, match="Integration not in pending status"):
            integration_handlers.handle_integration_approval(
                integration_id=integration_id,
                payload=payload,
                approved_by="admin@example.com",
            )


class TestIntegrationGetEndpoint:
    """Test GET /integrations/{integrationId} endpoint."""

    def test_get_existing_integration(self):
        """Test retrieving an existing integration."""
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing",
                "requestedTargets": ["https://api.example.com/endpoint"],
            }
        )

        result = integration_handlers.handle_integration_get(integration_id)

        assert result["id"] == integration_id
        assert result["name"] == "test-integration"
        assert result["status"] == "pending"

    def test_get_nonexistent_integration(self):
        """Test retrieving a non-existent integration."""
        fake_id = uuid.uuid4().hex

        with pytest.raises(ValueError, match=f"Integration not found: {fake_id}"):
            integration_handlers.handle_integration_get(fake_id)


class TestIntegrationsListEndpoint:
    """Test GET /integrations endpoint."""

    def test_list_all_integrations(self):
        """Test listing all integrations."""
        # Create multiple integrations
        integrations.request_integration(
            {
                "name": "integration-1",
                "justification": "First",
                "requestedTargets": ["https://api1.example.com"],
            }
        )
        integrations.request_integration(
            {
                "name": "integration-2",
                "justification": "Second",
                "requestedTargets": ["https://api2.example.com"],
            }
        )

        result = integration_handlers.handle_integrations_list()

        assert result["count"] == 2
        assert len(result["integrations"]) == 2
        assert result["status_filter"] is None

    def test_list_integrations_by_status(self):
        """Test listing integrations filtered by status."""
        id1 = integrations.request_integration(
            {
                "name": "pending-integration",
                "justification": "Will stay pending",
                "requestedTargets": ["https://api1.example.com"],
            }
        )

        id2 = integrations.request_integration(
            {
                "name": "active-integration",
                "justification": "Will be approved",
                "requestedTargets": ["https://api2.example.com"],
            }
        )

        # Approve one
        integrations.approve_integration(
            integration_id=id2,
            approved_targets=["https://api2.example.com"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # List only pending
        result = integration_handlers.handle_integrations_list(status="pending")
        assert result["count"] == 1
        assert result["integrations"][0]["id"] == id1

        # List only active
        result = integration_handlers.handle_integrations_list(status="active")
        assert result["count"] == 1
        assert result["integrations"][0]["id"] == id2

    def test_list_integrations_empty(self):
        """Test listing when no integrations exist."""
        result = integration_handlers.handle_integrations_list()

        assert result["count"] == 0
        assert result["integrations"] == []


class TestIntegrationAccessCheck:
    """Test check_integration_access function."""

    def test_access_approved_target(self):
        """Test access is granted for approved target."""
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing",
                "requestedTargets": ["https://api.example.com/endpoint1"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/endpoint1"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/endpoint1",
        )

        assert authorized is True

    def test_access_unapproved_target(self):
        """Test access is denied for unapproved target."""
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing",
                "requestedTargets": [
                    "https://api.example.com/endpoint1",
                    "https://api.example.com/endpoint2",
                ],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/endpoint1"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/endpoint2",
        )

        assert authorized is False

    def test_access_nonexistent_integration(self):
        """Test access is denied for non-existent integration."""
        fake_id = uuid.uuid4().hex

        authorized = integration_handlers.check_integration_access(
            integration_id=fake_id,
            target="https://api.example.com/endpoint",
        )

        assert authorized is False

    def test_access_pending_integration(self):
        """Test access is denied for pending integration."""
        integration_id = integrations.request_integration(
            {
                "name": "test-integration",
                "justification": "Testing",
                "requestedTargets": ["https://api.example.com/endpoint"],
            }
        )

        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/endpoint",
        )

        assert authorized is False
