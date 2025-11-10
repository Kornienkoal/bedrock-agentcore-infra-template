"""Contract tests for revocation management endpoints."""

from __future__ import annotations

import uuid

import pytest
from agentcore_governance import revocation
from agentcore_governance.api import revocation_handlers


@pytest.fixture(autouse=True)
def reset_revocation_registry():
    """Reset revocation registry before each test."""
    revocation._revocations_registry.clear()
    yield
    revocation._revocations_registry.clear()


class TestRevocationRequestEndpoint:
    """Test POST /revocations endpoint contract."""

    def test_successful_revocation_request(self):
        """Test successful revocation request with all required fields."""
        payload = {
            "subjectType": "user",
            "subjectId": "user-12345",
            "scope": "user_access",
            "reason": "Security incident - compromised credentials",
            "initiatedBy": "security-team",
        }

        response = revocation_handlers.handle_revocation_request(payload)

        # Verify response structure
        assert "revocation_id" in response
        assert "status" in response
        assert "correlation_id" in response
        assert response["status"] == "pending"

        # Verify revocation was created
        revocation_record = revocation.get_revocation_status(response["revocation_id"])
        assert revocation_record is not None
        assert revocation_record["subject_type"] == "user"
        assert revocation_record["subject_id"] == "user-12345"
        assert revocation_record["status"] == "pending"

    def test_revocation_request_minimal_fields(self):
        """Test revocation with only required fields."""
        payload = {
            "subjectType": "integration",
            "subjectId": "integration-abc",
            "scope": "integration_access",
        }

        response = revocation_handlers.handle_revocation_request(payload)

        assert response["status"] == "pending"

        revocation_record = revocation.get_revocation_status(response["revocation_id"])
        assert revocation_record["reason"] == ""
        assert revocation_record["initiated_by"] == "unknown"

    def test_missing_required_field_subject_type(self):
        """Test request fails when subjectType is missing."""
        payload = {
            "subjectId": "user-123",
            "scope": "user_access",
        }

        with pytest.raises(ValueError, match="Missing required field: subjectType"):
            revocation_handlers.handle_revocation_request(payload)

    def test_missing_required_field_subject_id(self):
        """Test request fails when subjectId is missing."""
        payload = {
            "subjectType": "user",
            "scope": "user_access",
        }

        with pytest.raises(ValueError, match="Missing required field: subjectId"):
            revocation_handlers.handle_revocation_request(payload)

    def test_missing_required_field_scope(self):
        """Test request fails when scope is missing."""
        payload = {
            "subjectType": "user",
            "subjectId": "user-123",
        }

        with pytest.raises(ValueError, match="Missing required field: scope"):
            revocation_handlers.handle_revocation_request(payload)

    def test_invalid_subject_type(self):
        """Test request fails with invalid subjectType."""
        payload = {
            "subjectType": "invalid_type",
            "subjectId": "user-123",
            "scope": "user_access",
        }

        with pytest.raises(ValueError, match="Invalid subjectType"):
            revocation_handlers.handle_revocation_request(payload)

    def test_invalid_scope(self):
        """Test request fails with invalid scope."""
        payload = {
            "subjectType": "user",
            "subjectId": "user-123",
            "scope": "invalid_scope",
        }

        with pytest.raises(ValueError, match="Invalid scope"):
            revocation_handlers.handle_revocation_request(payload)

    def test_all_subject_types(self):
        """Test all valid subject types."""
        subject_types = ["user", "integration", "tool", "agent", "principal"]

        for subject_type in subject_types:
            payload = {
                "subjectType": subject_type,
                "subjectId": f"{subject_type}-test",
                "scope": "user_access",
            }

            response = revocation_handlers.handle_revocation_request(payload)
            assert response["status"] == "pending"

    def test_all_scopes(self):
        """Test all valid scopes."""
        scopes = [
            "user_access",
            "tool_access",
            "integration_access",
            "principal_assume",
        ]

        for scope in scopes:
            payload = {
                "subjectType": "user",
                "subjectId": f"user-{scope}",
                "scope": scope,
            }

            response = revocation_handlers.handle_revocation_request(payload)
            assert response["status"] == "pending"


class TestRevocationGetEndpoint:
    """Test GET /revocations/{revocationId} endpoint contract."""

    def test_get_existing_revocation(self):
        """Test retrieving an existing revocation."""
        # Create revocation
        revocation_id = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
                "reason": "Test",
            }
        )

        # Retrieve it
        result = revocation_handlers.handle_revocation_get(revocation_id)

        assert result["id"] == revocation_id
        assert result["subject_type"] == "user"
        assert result["subject_id"] == "user-123"
        assert result["status"] == "pending"

    def test_get_nonexistent_revocation(self):
        """Test retrieving a non-existent revocation."""
        fake_id = uuid.uuid4().hex

        with pytest.raises(ValueError, match=f"Revocation not found: {fake_id}"):
            revocation_handlers.handle_revocation_get(fake_id)

    def test_get_complete_revocation_includes_sla(self):
        """Test that completed revocations include SLA status."""
        # Create and complete revocation
        revocation_id = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        revocation.mark_revocation_propagated(revocation_id)

        # Retrieve it
        result = revocation_handlers.handle_revocation_get(revocation_id)

        assert result["status"] == "complete"
        assert "sla_met" in result
        assert "sla_status" in result
        assert result["sla_status"] in ["met", "breached"]


class TestRevocationPropagateEndpoint:
    """Test revocation propagation handler (internal use)."""

    def test_successful_propagation(self):
        """Test successful revocation propagation."""
        # Create revocation
        revocation_id = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        # Propagate it
        response = revocation_handlers.handle_revocation_propagate(revocation_id)

        assert response["revocation_id"] == revocation_id
        assert response["status"] == "complete"
        assert "propagation_latency_ms" in response
        assert "sla_met" in response
        assert "metric" in response

    def test_propagate_nonexistent_revocation(self):
        """Test propagating a non-existent revocation."""
        fake_id = uuid.uuid4().hex

        with pytest.raises(ValueError, match=f"Revocation not found: {fake_id}"):
            revocation_handlers.handle_revocation_propagate(fake_id)

    def test_propagate_already_propagated(self):
        """Test propagating an already propagated revocation."""
        # Create and propagate
        revocation_id = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        revocation_handlers.handle_revocation_propagate(revocation_id)

        # Try to propagate again
        with pytest.raises(ValueError, match="already propagated"):
            revocation_handlers.handle_revocation_propagate(revocation_id)


class TestRevocationsListEndpoint:
    """Test GET /revocations endpoint."""

    def test_list_all_revocations(self):
        """Test listing all revocations."""
        # Create multiple revocations
        revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-1",
                "scope": "user_access",
            }
        )
        revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-2",
                "scope": "user_access",
            }
        )

        result = revocation_handlers.handle_revocations_list()

        assert result["count"] == 2
        assert len(result["revocations"]) == 2
        assert "sla_metrics" in result

    def test_list_by_status(self):
        """Test listing revocations filtered by status."""
        # Create pending and complete revocations
        id1 = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-pending",
                "scope": "user_access",
            }
        )

        id2 = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-complete",
                "scope": "user_access",
            }
        )

        revocation.mark_revocation_propagated(id2)

        # List only pending
        result = revocation_handlers.handle_revocations_list(status="pending")
        assert result["count"] == 1
        assert result["revocations"][0]["id"] == id1

        # List only complete
        result = revocation_handlers.handle_revocations_list(status="complete")
        assert result["count"] == 1
        assert result["revocations"][0]["id"] == id2

    def test_list_by_subject_type(self):
        """Test listing revocations filtered by subject type."""
        revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-1",
                "scope": "user_access",
            }
        )

        revocation.create_revocation_request(
            {
                "subjectType": "integration",
                "subjectId": "integration-1",
                "scope": "integration_access",
            }
        )

        # List only users
        result = revocation_handlers.handle_revocations_list(subject_type="user")
        assert result["count"] == 1
        assert result["revocations"][0]["subject_type"] == "user"

        # List only integrations
        result = revocation_handlers.handle_revocations_list(subject_type="integration")
        assert result["count"] == 1
        assert result["revocations"][0]["subject_type"] == "integration"

    def test_list_empty(self):
        """Test listing when no revocations exist."""
        result = revocation_handlers.handle_revocations_list()

        assert result["count"] == 0
        assert result["revocations"] == []
        assert result["sla_metrics"]["total_revocations"] == 0


class TestCheckSubjectRevokedFunction:
    """Test check_subject_revoked function."""

    def test_subject_not_revoked(self):
        """Test checking a subject that is not revoked."""
        is_revoked = revocation_handlers.check_subject_revoked("user", "user-123")
        assert is_revoked is False

    def test_subject_with_pending_revocation(self):
        """Test subject with pending revocation is blocked."""
        revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        is_revoked = revocation_handlers.check_subject_revoked("user", "user-123")
        assert is_revoked is True

    def test_subject_with_complete_revocation(self):
        """Test subject with complete revocation is blocked."""
        revocation_id = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        revocation.mark_revocation_propagated(revocation_id)

        is_revoked = revocation_handlers.check_subject_revoked("user", "user-123")
        assert is_revoked is True

    def test_subject_with_failed_revocation_not_blocked(self):
        """Test subject with failed revocation is not blocked."""
        revocation_id = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        revocation.mark_revocation_failed(revocation_id, "Test error")

        is_revoked = revocation_handlers.check_subject_revoked("user", "user-123")
        assert is_revoked is False

    def test_check_with_attempted_action_emits_audit(self):
        """Test that checking with attempted action emits audit event."""
        revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        # This should emit an audit event
        is_revoked = revocation_handlers.check_subject_revoked(
            subject_type="user", subject_id="user-123", attempted_action="login"
        )

        assert is_revoked is True
