"""Integration denial path tests."""

from __future__ import annotations

import pytest
from agentcore_governance import integrations
from agentcore_governance.api import integration_handlers


@pytest.fixture(autouse=True)
def reset_integration_registry():
    """Reset integration registry before each test."""
    integrations._integrations_registry.clear()
    yield
    integrations._integrations_registry.clear()


class TestIntegrationDenialPath:
    """Test access denial scenarios for third-party integrations."""

    def test_deny_unapproved_integration_access(self):
        """Test that unapproved integrations cannot access any targets."""
        # Create a pending integration
        integration_id = integrations.request_integration(
            {
                "name": "pending-integration",
                "justification": "Awaiting approval",
                "requestedTargets": [
                    "https://api.example.com/users",
                    "https://api.example.com/orders",
                ],
            }
        )

        # Attempt to access targets before approval
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/users",
        )
        assert authorized is False

        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/orders",
        )
        assert authorized is False

    def test_deny_unauthorized_target_access(self):
        """Test that approved integrations can only access approved targets."""
        # Create and approve integration with limited targets
        integration_id = integrations.request_integration(
            {
                "name": "limited-integration",
                "justification": "Limited scope integration",
                "requestedTargets": [
                    "https://api.example.com/public/users",
                    "https://api.example.com/admin/users",
                    "https://api.example.com/admin/settings",
                ],
            }
        )

        # Approve only public endpoints
        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/public/users"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Verify approved target is accessible
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/public/users",
        )
        assert authorized is True

        # Verify unapproved targets are denied
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/admin/users",
        )
        assert authorized is False

        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/admin/settings",
        )
        assert authorized is False

    def test_deny_unrequested_target_access(self):
        """Test that integrations cannot access targets not in original request."""
        integration_id = integrations.request_integration(
            {
                "name": "scoped-integration",
                "justification": "Specific scope only",
                "requestedTargets": ["https://api.example.com/v1/data"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/v1/data"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Verify approved target works
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/v1/data",
        )
        assert authorized is True

        # Verify other targets are denied (even if similar)
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/v2/data",
        )
        assert authorized is False

        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/v1/admin",
        )
        assert authorized is False

    def test_deny_revoked_integration_access(self):
        """Test that revoked integrations lose all access."""
        # Create and approve integration
        integration_id = integrations.request_integration(
            {
                "name": "revokable-integration",
                "justification": "Will be revoked",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/data"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Verify access works initially
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/data",
        )
        assert authorized is True

        # Revoke the integration
        integrations.revoke_integration(
            integration_id=integration_id,
            reason="Security incident",
        )

        # Verify access is now denied
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/data",
        )
        assert authorized is False

    def test_deny_nonexistent_integration_access(self):
        """Test that non-existent integrations have no access."""
        fake_id = "00000000000000000000000000000000"

        authorized = integration_handlers.check_integration_access(
            integration_id=fake_id,
            target="https://api.example.com/any",
        )
        assert authorized is False

    def test_deny_case_sensitive_target_mismatch(self):
        """Test that target matching is case-sensitive."""
        integration_id = integrations.request_integration(
            {
                "name": "case-sensitive-integration",
                "justification": "Testing case sensitivity",
                "requestedTargets": ["https://api.example.com/Users"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/Users"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Verify exact match works
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/Users",
        )
        assert authorized is True

        # Verify case differences are denied
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/users",
        )
        assert authorized is False

        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/USERS",
        )
        assert authorized is False

    def test_partial_target_approval_denial(self):
        """Test that subset approval denies remaining targets."""
        integration_id = integrations.request_integration(
            {
                "name": "partial-approval-integration",
                "justification": "Requesting multiple targets",
                "requestedTargets": [
                    "https://api.example.com/endpoint1",
                    "https://api.example.com/endpoint2",
                    "https://api.example.com/endpoint3",
                ],
            }
        )

        # Approve only first and third targets
        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=[
                "https://api.example.com/endpoint1",
                "https://api.example.com/endpoint3",
            ],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Verify approved targets
        assert (
            integration_handlers.check_integration_access(
                integration_id=integration_id,
                target="https://api.example.com/endpoint1",
            )
            is True
        )

        assert (
            integration_handlers.check_integration_access(
                integration_id=integration_id,
                target="https://api.example.com/endpoint3",
            )
            is True
        )

        # Verify denied target
        assert (
            integration_handlers.check_integration_access(
                integration_id=integration_id,
                target="https://api.example.com/endpoint2",
            )
            is False
        )

    def test_empty_approved_targets_denies_all(self):
        """Test that approving with no targets denies all access."""
        integration_id = integrations.request_integration(
            {
                "name": "empty-approval-integration",
                "justification": "Will have empty approval",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        # Approve with empty targets list
        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=[],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Verify access is denied even for requested target
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/data",
        )
        assert authorized is False
