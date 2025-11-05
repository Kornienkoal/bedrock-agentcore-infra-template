"""Integration test for evidence pack generation."""

from unittest.mock import patch

from agentcore_governance import evidence


class TestEvidencePackGeneration:
    """Integration tests for evidence pack generation."""

    @patch("agentcore_governance.catalog.fetch_principal_catalog")
    def test_build_evidence_pack_baseline(self, mock_fetch):
        """Test baseline evidence pack generation."""
        # Mock catalog response
        mock_fetch.return_value = [
            {
                "id": "arn:aws:iam::123456789012:role/test-role",
                "least_privilege_score": 85.0,
            },
            {
                "id": "arn:aws:iam::123456789012:role/another-role",
                "least_privilege_score": 92.0,
            },
        ]

        pack = evidence.build_evidence_pack()

        assert "id" in pack
        assert "generated_at" in pack
        assert pack["principal_snapshot_count"] == 2
        assert pack["audit_event_range_hours"] == 24
        assert pack["conformance_score"] > 0
        assert "missing_events" in pack

    @patch("agentcore_governance.catalog.fetch_principal_catalog")
    def test_build_evidence_pack_custom_hours(self, mock_fetch):
        """Test evidence pack with custom hours_back parameter."""
        mock_fetch.return_value = []

        pack = evidence.build_evidence_pack({"hours_back": 48})

        assert pack["audit_event_range_hours"] == 48

    @patch("agentcore_governance.catalog.fetch_principal_catalog")
    def test_build_evidence_pack_handles_catalog_error(self, mock_fetch):
        """Test evidence pack generation when catalog fetch fails."""
        mock_fetch.side_effect = Exception("Catalog error")

        pack = evidence.build_evidence_pack()

        # Should still generate pack with zero principals
        assert pack["principal_snapshot_count"] == 0
        assert "id" in pack


class TestConstructAuditEvent:
    """Integration tests for audit event construction."""

    def test_construct_complete_audit_event(self):
        """Test constructing a complete audit event."""
        event = evidence.construct_audit_event(
            event_type="tool_invocation",
            correlation_id="trace=abc123;agent=customer-support;tool=web_search",
            principal_chain=["user:alice@example.com", "agent:customer-support", "tool:web_search"],
            outcome="success",
            latency_ms=250,
            additional_fields={"request_id": "req-456"},
        )

        assert event["event_type"] == "tool_invocation"
        assert event["correlation_id"] == "trace=abc123;agent=customer-support;tool=web_search"
        assert len(event["principal_chain"]) == 3
        assert event["outcome"] == "success"
        assert event["latency_ms"] == 250
        assert event["request_id"] == "req-456"
        assert "integrity_hash" in event
        assert len(event["integrity_hash"]) == 64  # SHA256 hex

    def test_audit_event_integrity_hash_consistency(self):
        """Test that audit event integrity hash is consistent."""
        event1 = evidence.construct_audit_event(
            event_type="agent_invocation",
            correlation_id="trace=xyz",
            principal_chain=["user:bob"],
            outcome="success",
        )

        # Construct same event (will have different ID and timestamp)
        event2 = evidence.construct_audit_event(
            event_type="agent_invocation",
            correlation_id="trace=xyz",
            principal_chain=["user:bob"],
            outcome="success",
        )

        # Hashes should be different because ID and timestamp differ
        assert event1["integrity_hash"] != event2["integrity_hash"]

    def test_audit_event_minimal_fields(self):
        """Test constructing audit event with minimal fields."""
        event = evidence.construct_audit_event(
            event_type="memory_access",
            correlation_id="trace=minimal",
            principal_chain=["agent:test"],
            outcome="denied",
        )

        assert event["latency_ms"] == 0
        assert "integrity_hash" in event
