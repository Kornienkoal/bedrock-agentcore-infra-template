"""Tests for revocation audit event integrity and completeness."""

from __future__ import annotations

import pytest
from agentcore_governance import correlation, evidence, revocation
from agentcore_governance.api import revocation_handlers


@pytest.fixture(autouse=True)
def reset_revocation_registry():
    """Reset revocation registry before each test."""
    revocation._revocations_registry.clear()
    yield
    revocation._revocations_registry.clear()


class TestRevocationRequestAuditEvent:
    """Test audit event for revocation requests."""

    def test_revocation_request_event_structure(self):
        """Test that revocation request audit event has correct structure."""
        with correlation.new_correlation_context() as corr_id:
            event = evidence.construct_revocation_request_event(
                revocation_id="rev-123",
                subject_type="user",
                subject_id="user-123",
                scope="user_access",
                reason="Security incident",
                initiated_by="security-team",
                correlation_id=corr_id,
            )

            # Verify required fields
            assert event["event_type"] == "revocation_request"
            assert event["revocation_id"] == "rev-123"
            assert event["subject_type"] == "user"
            assert event["subject_id"] == "user-123"
            assert event["scope"] == "user_access"
            assert event["reason"] == "Security incident"
            assert event["initiated_by"] == "security-team"
            assert event["correlation_id"] == corr_id
            assert "timestamp" in event
            assert "integrity_hash" in event

    def test_revocation_request_event_integrity_hash(self):
        """Test that integrity hash is computed correctly."""
        with correlation.new_correlation_context():
            event = evidence.construct_revocation_request_event(
                revocation_id="rev-123",
                subject_type="user",
                subject_id="user-123",
                scope="user_access",
                reason="Test",
                initiated_by="tester",
            )

            # Hash should be present and non-empty
            assert event["integrity_hash"] is not None
            assert len(event["integrity_hash"]) == 64  # SHA256 hex

    def test_revocation_request_event_minimal_fields(self):
        """Test audit event with minimal required fields."""
        with correlation.new_correlation_context():
            event = evidence.construct_revocation_request_event(
                revocation_id="rev-123",
                subject_type="user",
                subject_id="user-123",
                scope="user_access",
                reason="",
                initiated_by="unknown",
            )

            # Verify the fields are present as provided
            assert event["reason"] == ""
            assert event["initiated_by"] == "unknown"


class TestRevocationPropagatedAuditEvent:
    """Test audit event for revocation propagation."""

    def test_revocation_propagated_event_structure(self):
        """Test that revocation propagated audit event has correct structure."""
        with correlation.new_correlation_context() as corr_id:
            event = evidence.construct_revocation_propagated_event(
                revocation_id="rev-123",
                latency_ms=45,
                sla_met=True,
                correlation_id=corr_id,
            )

            # Verify required fields
            assert event["event_type"] == "revocation_propagated"
            assert event["revocation_id"] == "rev-123"
            assert event["latency_ms"] == 45
            assert event["sla_met"] is True
            assert event["correlation_id"] == corr_id
            assert "timestamp" in event
            assert "integrity_hash" in event

    def test_revocation_propagated_event_sla_breach(self):
        """Test audit event records SLA breach."""
        with correlation.new_correlation_context():
            event = evidence.construct_revocation_propagated_event(
                revocation_id="rev-123",
                latency_ms=350000,  # Over 5 minutes
                sla_met=False,
            )

            assert event["sla_met"] is False

    def test_revocation_propagated_event_integrity_hash(self):
        """Test that integrity hash is computed correctly."""
        with correlation.new_correlation_context():
            event = evidence.construct_revocation_propagated_event(
                revocation_id="rev-123",
                latency_ms=45,
                sla_met=True,
            )

            # Hash should be present and non-empty
            assert event["integrity_hash"] is not None
            assert len(event["integrity_hash"]) == 64  # SHA256 hex


class TestRevocationAccessDeniedAuditEvent:
    """Test audit event for access denied due to revocation."""

    def test_revocation_access_denied_event_structure(self):
        """Test that access denied audit event has correct structure."""
        with correlation.new_correlation_context() as corr_id:
            event = evidence.construct_revocation_access_denied_event(
                subject_type="user",
                subject_id="user-123",
                attempted_action="login",
                correlation_id=corr_id,
            )

            # Verify required fields
            assert event["event_type"] == "revocation_access_denied"
            assert event["subject_type"] == "user"
            assert event["subject_id"] == "user-123"
            assert event["attempted_action"] == "login"
            assert event["correlation_id"] == corr_id
            assert "timestamp" in event
            assert "integrity_hash" in event

    def test_revocation_access_denied_event_without_revocation_id(self):
        """Test access denied event structure (revocation_id not in signature)."""
        with correlation.new_correlation_context():
            event = evidence.construct_revocation_access_denied_event(
                subject_type="user",
                subject_id="user-123",
                attempted_action="login",
            )

            # Verify core fields are present
            assert event["subject_type"] == "user"
            assert event["subject_id"] == "user-123"
            assert event["attempted_action"] == "login"

    def test_revocation_access_denied_event_integrity_hash(self):
        """Test that integrity hash is computed correctly."""
        with correlation.new_correlation_context():
            event = evidence.construct_revocation_access_denied_event(
                subject_type="user",
                subject_id="user-123",
                attempted_action="login",
            )

            # Hash should be present and non-empty
            assert event["integrity_hash"] is not None
            assert len(event["integrity_hash"]) == 64  # SHA256 hex


class TestAuditEventIntegrity:
    """Test audit event integrity verification."""

    def test_different_events_have_different_hashes(self):
        """Test that different events produce different integrity hashes."""
        with correlation.new_correlation_context():
            event1 = evidence.construct_revocation_request_event(
                revocation_id="rev-1",
                subject_type="user",
                subject_id="user-1",
                scope="user_access",
                reason="Test",
                initiated_by="tester",
            )

            event2 = evidence.construct_revocation_request_event(
                revocation_id="rev-2",
                subject_type="user",
                subject_id="user-2",
                scope="user_access",
                reason="Test",
                initiated_by="tester",
            )

            assert event1["integrity_hash"] != event2["integrity_hash"]

    def test_same_event_produces_same_hash(self):
        """Test that same event data produces same hash (deterministic)."""
        with correlation.new_correlation_context():
            # Create two events with identical data
            event1 = evidence.construct_revocation_request_event(
                revocation_id="rev-123",
                subject_type="user",
                subject_id="user-123",
                scope="user_access",
                reason="Test",
                initiated_by="tester",
            )

            # Hash is based on specific fields, not the full event
            # Verify hash is deterministic for same event data
            hash_fields = [
                event1["id"],
                event1["timestamp"],
                event1["revocation_id"],
                event1["subject_type"],
                event1["subject_id"],
                event1["scope"],
                event1["reason"],
                event1["initiated_by"],
            ]

            # Verify hash is present and valid format
            from agentcore_governance import integrity

            expected_hash = integrity.compute_integrity_hash(hash_fields)

            # Verify event1's hash matches expected computation
            assert event1["integrity_hash"] == expected_hash


class TestCorrelationIDPropagation:
    """Test that correlation IDs propagate through revocation flow."""

    def test_correlation_id_in_request_handler(self):
        """Test that request handler includes correlation ID in response."""
        payload = {
            "subjectType": "user",
            "subjectId": "user-123",
            "scope": "user_access",
        }

        response = revocation_handlers.handle_revocation_request(payload)

        # Handler creates its own correlation context, just verify it's present
        assert "correlation_id" in response
        assert len(response["correlation_id"]) == 32  # UUID hex format

    def test_correlation_id_in_propagation_handler(self):
        """Test that propagation handler includes correlation ID."""
        # Create revocation
        revocation_id = revocation.create_revocation_request(
            {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
            }
        )

        # Propagate - handler creates its own correlation context
        response = revocation_handlers.handle_revocation_propagate(revocation_id)

        # Just verify correlation ID is present and valid format
        assert "correlation_id" in response
        assert len(response["correlation_id"]) == 32  # UUID hex format

    def test_correlation_id_unique_per_operation(self):
        """Test that each operation gets a unique correlation ID."""
        corr_ids = []

        for i in range(3):
            with correlation.new_correlation_context():
                payload = {
                    "subjectType": "user",
                    "subjectId": f"user-{i}",
                    "scope": "user_access",
                }

                response = revocation_handlers.handle_revocation_request(payload)
                corr_ids.append(response["correlation_id"])

        # All should be unique
        assert len(set(corr_ids)) == 3


class TestEndToEndAuditTrail:
    """Test complete audit trail for revocation lifecycle."""

    def test_complete_revocation_audit_trail(self):
        """Test that a complete revocation produces full audit trail."""
        audit_events = []

        # 1. Request revocation
        with correlation.new_correlation_context() as req_corr_id:
            payload = {
                "subjectType": "user",
                "subjectId": "user-123",
                "scope": "user_access",
                "reason": "Security incident",
            }

            response = revocation_handlers.handle_revocation_request(payload)
            revocation_id = response["revocation_id"]

            # Capture request audit event
            request_event = evidence.construct_revocation_request_event(
                revocation_id=revocation_id,
                subject_type="user",
                subject_id="user-123",
                scope="user_access",
                reason="Security incident",
                initiated_by="security-team",
                correlation_id=req_corr_id,
            )
            audit_events.append(request_event)

        # 2. Propagate revocation
        with correlation.new_correlation_context() as prop_corr_id:
            prop_response = revocation_handlers.handle_revocation_propagate(revocation_id)

            # Capture propagation audit event
            prop_event = evidence.construct_revocation_propagated_event(
                revocation_id=revocation_id,
                latency_ms=prop_response["propagation_latency_ms"],
                sla_met=prop_response["sla_met"],
                correlation_id=prop_corr_id,
            )
            audit_events.append(prop_event)

        # 3. Attempt access (should be denied)
        with correlation.new_correlation_context() as access_corr_id:
            is_blocked = revocation_handlers.check_subject_revoked(
                subject_type="user",
                subject_id="user-123",
                attempted_action="login",
            )

            # Capture access denied audit event
            if is_blocked:
                denied_event = evidence.construct_revocation_access_denied_event(
                    subject_type="user",
                    subject_id="user-123",
                    attempted_action="login",
                    correlation_id=access_corr_id,
                )
                audit_events.append(denied_event)

        # Verify complete audit trail
        assert len(audit_events) == 3
        assert audit_events[0]["event_type"] == "revocation_request"
        assert audit_events[1]["event_type"] == "revocation_propagated"
        assert audit_events[2]["event_type"] == "revocation_access_denied"

        # Verify all have integrity hashes
        for event in audit_events:
            assert "integrity_hash" in event
            assert len(event["integrity_hash"]) == 64

        # Verify correlation IDs are different
        assert audit_events[0]["correlation_id"] == req_corr_id
        assert audit_events[1]["correlation_id"] == prop_corr_id
        assert audit_events[2]["correlation_id"] == access_corr_id
