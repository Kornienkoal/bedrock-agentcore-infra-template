"""Integration expiry scenario tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from agentcore_governance import integrations
from agentcore_governance.api import integration_handlers


@pytest.fixture(autouse=True)
def reset_integration_registry():
    """Reset integration registry before each test."""
    integrations._integrations_registry.clear()
    yield
    integrations._integrations_registry.clear()


class TestIntegrationExpiry:
    """Test integration expiry scenarios."""

    def test_integration_expires_after_duration(self):
        """Test that integration expires after specified duration."""
        # Create and approve integration with 1 day expiry
        integration_id = integrations.request_integration(
            {
                "name": "expiring-integration",
                "justification": "Short-term integration",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/data"],
            expiry_days=1,
            approved_by="admin@example.com",
        )

        integration = integrations.get_integration(integration_id)
        assert integration["status"] == "active"
        assert integration["expires_at"] is not None

        # Verify access works before expiry
        authorized = integration_handlers.check_integration_access(
            integration_id=integration_id,
            target="https://api.example.com/data",
        )
        assert authorized is True

        # Mock time to 2 days in the future
        future_time = datetime.now(UTC) + timedelta(days=2)
        with patch("agentcore_governance.integrations.datetime") as mock_datetime:
            mock_datetime.now.return_value = future_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Check access again - should be denied and marked expired
            authorized = integration_handlers.check_integration_access(
                integration_id=integration_id,
                target="https://api.example.com/data",
            )
            assert authorized is False

            # Verify status changed to expired
            integration = integrations.get_integration(integration_id)
            assert integration["status"] == "expired"

    def test_integration_without_expiry_never_expires(self):
        """Test that integrations without expiry remain active."""
        integration_id = integrations.request_integration(
            {
                "name": "permanent-integration",
                "justification": "Long-term integration",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/data"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        integration = integrations.get_integration(integration_id)
        assert integration["expires_at"] is None
        assert integration["status"] == "active"

        # Mock far future time
        future_time = datetime.now(UTC) + timedelta(days=365 * 10)
        with patch("agentcore_governance.integrations.datetime") as mock_datetime:
            mock_datetime.now.return_value = future_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Should still have access
            authorized = integration_handlers.check_integration_access(
                integration_id=integration_id,
                target="https://api.example.com/data",
            )
            assert authorized is True

            # Status should remain active
            integration = integrations.get_integration(integration_id)
            assert integration["status"] == "active"

    def test_mark_expired_integrations_batch(self):
        """Test batch marking of expired integrations."""
        # Create multiple integrations with different expiry dates
        now = datetime.now(UTC)

        # Integration 1: Already expired (approved 5 days ago with 3 day expiry)
        id1 = integrations.request_integration(
            {
                "name": "expired-1",
                "justification": "Should be expired",
                "requestedTargets": ["https://api1.example.com/data"],
            }
        )
        integrations.approve_integration(
            integration_id=id1,
            approved_targets=["https://api1.example.com/data"],
            expiry_days=3,
            approved_by="admin@example.com",
        )
        # Manually set approved_at to past
        integrations._integrations_registry[id1]["approved_at"] = (
            now - timedelta(days=5)
        ).isoformat()
        integrations._integrations_registry[id1]["expires_at"] = (
            now - timedelta(days=2)
        ).isoformat()

        # Integration 2: Will expire soon (approved 2 days ago with 3 day expiry)
        id2 = integrations.request_integration(
            {
                "name": "expiring-soon",
                "justification": "Will expire soon",
                "requestedTargets": ["https://api2.example.com/data"],
            }
        )
        integrations.approve_integration(
            integration_id=id2,
            approved_targets=["https://api2.example.com/data"],
            expiry_days=3,
            approved_by="admin@example.com",
        )
        integrations._integrations_registry[id2]["approved_at"] = (
            now - timedelta(days=2)
        ).isoformat()
        integrations._integrations_registry[id2]["expires_at"] = (
            now + timedelta(days=1)
        ).isoformat()

        # Integration 3: No expiry
        id3 = integrations.request_integration(
            {
                "name": "no-expiry",
                "justification": "Permanent",
                "requestedTargets": ["https://api3.example.com/data"],
            }
        )
        integrations.approve_integration(
            integration_id=id3,
            approved_targets=["https://api3.example.com/data"],
            expiry_days=None,
            approved_by="admin@example.com",
        )

        # Run batch expiry check
        expired_count = integrations.mark_expired_integrations()

        # Should mark 1 integration as expired
        assert expired_count == 1

        # Verify statuses
        assert integrations.get_integration(id1)["status"] == "expired"
        assert integrations.get_integration(id2)["status"] == "active"
        assert integrations.get_integration(id3)["status"] == "active"

    def test_expiry_duration_calculation(self):
        """Test that expiry date is calculated correctly."""
        integration_id = integrations.request_integration(
            {
                "name": "test-expiry-calc",
                "justification": "Testing calculation",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/data"],
            expiry_days=30,
            approved_by="admin@example.com",
        )

        integration = integrations.get_integration(integration_id)
        expires_at = datetime.fromisoformat(integration["expires_at"])
        approved_at = datetime.fromisoformat(integration["approved_at"])

        # Calculate difference
        diff = expires_at - approved_at

        # Should be approximately 30 days (allow small margin for test execution time)
        assert 29.99 <= diff.total_seconds() / 86400 <= 30.01

    def test_expired_integration_status_persists(self):
        """Test that expired status persists across checks."""
        integration_id = integrations.request_integration(
            {
                "name": "expire-persist-test",
                "justification": "Testing persistence",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/data"],
            expiry_days=1,
            approved_by="admin@example.com",
        )

        # Mock time to after expiry
        future_time = datetime.now(UTC) + timedelta(days=2)
        with patch("agentcore_governance.integrations.datetime") as mock_datetime:
            mock_datetime.now.return_value = future_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            # First check - triggers expiry
            integration_handlers.check_integration_access(
                integration_id=integration_id,
                target="https://api.example.com/data",
            )

            # Second check - should still be expired
            authorized = integration_handlers.check_integration_access(
                integration_id=integration_id,
                target="https://api.example.com/data",
            )
            assert authorized is False

            integration = integrations.get_integration(integration_id)
            assert integration["status"] == "expired"

    def test_expiry_with_zero_days(self):
        """Test that zero expiry days are rejected."""
        integration_id = integrations.request_integration(
            {
                "name": "zero-expiry-test",
                "justification": "Testing zero days",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        # Should raise error for zero days
        with pytest.raises(ValueError, match="expiryDays must be a positive integer"):
            integration_handlers.handle_integration_approval(
                integration_id=integration_id,
                payload={
                    "approvedTargets": ["https://api.example.com/data"],
                    "expiryDays": 0,
                },
                approved_by="admin@example.com",
            )

    def test_batch_expiry_with_no_expired_integrations(self):
        """Test batch expiry when no integrations have expired."""
        # Create active integration with future expiry
        integration_id = integrations.request_integration(
            {
                "name": "active-integration",
                "justification": "Not expired",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )

        integrations.approve_integration(
            integration_id=integration_id,
            approved_targets=["https://api.example.com/data"],
            expiry_days=365,
            approved_by="admin@example.com",
        )

        # Run batch check
        expired_count = integrations.mark_expired_integrations()

        assert expired_count == 0
        assert integrations.get_integration(integration_id)["status"] == "active"

    def test_expiry_check_skips_non_active_integrations(self):
        """Test that batch expiry only processes active integrations."""
        # Create expired integration
        id1 = integrations.request_integration(
            {
                "name": "already-expired",
                "justification": "Already expired",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )
        integrations.approve_integration(
            integration_id=id1,
            approved_targets=["https://api.example.com/data"],
            expiry_days=1,
            approved_by="admin@example.com",
        )
        # Manually set as expired
        now = datetime.now(UTC)
        integrations._integrations_registry[id1]["expires_at"] = (
            now - timedelta(days=1)
        ).isoformat()
        integrations._integrations_registry[id1]["status"] = "expired"

        # Create revoked integration with past expiry
        id2 = integrations.request_integration(
            {
                "name": "revoked-integration",
                "justification": "Revoked",
                "requestedTargets": ["https://api.example.com/data"],
            }
        )
        integrations.approve_integration(
            integration_id=id2,
            approved_targets=["https://api.example.com/data"],
            expiry_days=1,
            approved_by="admin@example.com",
        )
        integrations.revoke_integration(id2, reason="Test")
        integrations._integrations_registry[id2]["expires_at"] = (
            now - timedelta(days=1)
        ).isoformat()

        # Run batch check - should not process already expired or revoked
        expired_count = integrations.mark_expired_integrations()

        assert expired_count == 0
        assert integrations.get_integration(id1)["status"] == "expired"
        assert integrations.get_integration(id2)["status"] == "revoked"
