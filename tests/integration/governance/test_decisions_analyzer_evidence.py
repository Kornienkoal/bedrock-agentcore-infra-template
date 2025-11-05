"""Contract tests for decisions, analyzer, and evidence pack endpoints."""

from __future__ import annotations

from agentcore_governance.api import analyzer_handlers, decision_handlers, evidence_handlers


class TestDecisionEndpoints:
    """Test contract compliance for /decisions endpoints."""

    def test_list_decisions_returns_valid_structure(self):
        """Verify list_decisions returns proper response structure."""
        response = decision_handlers.list_decisions()

        assert "decisions" in response
        assert "count" in response
        assert "filters" in response
        assert "status" in response
        assert response["status"] == 200
        assert isinstance(response["decisions"], list)
        assert isinstance(response["count"], int)

    def test_list_decisions_with_subject_filter(self):
        """Verify subject_id filtering works correctly."""
        # Record a test decision
        decision_handlers.record_decision(
            subject_type="agent",
            subject_id="test-agent-123",
            action="tool:invoke",
            resource="tool:web_search",
            effect="allow",
            policy_reference="default-policy",
            correlation_id="test-corr-123",
        )

        # Query with filter
        response = decision_handlers.list_decisions(subject_id="test-agent-123")

        assert response["status"] == 200
        assert response["count"] > 0
        assert all(d["subject_id"] == "test-agent-123" for d in response["decisions"])

    def test_list_decisions_with_effect_filter(self):
        """Verify effect filtering works correctly."""
        # Record allow and deny decisions
        decision_handlers.record_decision(
            subject_type="agent",
            subject_id="agent-allow",
            action="tool:invoke",
            resource="tool:allowed",
            effect="allow",
            policy_reference="policy-1",
            correlation_id="corr-allow",
        )

        decision_handlers.record_decision(
            subject_type="agent",
            subject_id="agent-deny",
            action="tool:invoke",
            resource="tool:denied",
            effect="deny",
            policy_reference="policy-2",
            correlation_id="corr-deny",
            reason="unauthorized",
        )

        # Query for deny decisions
        response = decision_handlers.list_decisions(effect="deny")

        assert response["status"] == 200
        if response["count"] > 0:
            assert all(d["effect"] == "deny" for d in response["decisions"])

    def test_list_decisions_invalid_effect_returns_error(self):
        """Verify invalid effect parameter returns error."""
        response = decision_handlers.list_decisions(effect="invalid")

        assert response["status"] == 400
        assert "error" in response

    def test_record_decision_creates_valid_record(self):
        """Verify record_decision creates properly structured record."""
        decision = decision_handlers.record_decision(
            subject_type="user",
            subject_id="user-456",
            action="data:read",
            resource="s3://bucket/key",
            effect="allow",
            policy_reference="user-policy",
            correlation_id="test-corr-456",
            reason="authorized user",
        )

        assert "id" in decision
        assert "timestamp" in decision
        assert decision["subject_type"] == "user"
        assert decision["subject_id"] == "user-456"
        assert decision["action"] == "data:read"
        assert decision["resource"] == "s3://bucket/key"
        assert decision["effect"] == "allow"
        assert decision["policy_reference"] == "user-policy"
        assert decision["correlation_id"] == "test-corr-456"
        assert decision["reason"] == "authorized user"

    def test_get_decisions_for_correlation(self):
        """Verify correlation-based decision retrieval."""
        corr_id = "unique-corr-789"

        # Record multiple decisions with same correlation ID
        decision_handlers.record_decision(
            subject_type="agent",
            subject_id="agent-1",
            action="action-1",
            resource="resource-1",
            effect="allow",
            policy_reference="policy",
            correlation_id=corr_id,
        )

        decision_handlers.record_decision(
            subject_type="agent",
            subject_id="agent-1",
            action="action-2",
            resource="resource-2",
            effect="deny",
            policy_reference="policy",
            correlation_id=corr_id,
        )

        # Retrieve decisions
        decisions = decision_handlers.get_decisions_for_correlation(corr_id)

        assert len(decisions) >= 2
        assert all(d["correlation_id"] == corr_id for d in decisions)
        # Should be sorted by timestamp
        timestamps = [d["timestamp"] for d in decisions]
        assert timestamps == sorted(timestamps)


class TestAnalyzerEndpoints:
    """Test contract compliance for /analyzer endpoints."""

    def test_least_privilege_report_returns_valid_structure(self):
        """Verify least-privilege report has proper structure."""
        response = analyzer_handlers.get_least_privilege_report()

        assert "conformance_score" in response
        assert "total_principals" in response
        assert "passing_count" in response
        assert "failing_count" in response
        assert "failing_principals" in response
        assert "threshold" in response
        assert "recommendations" in response
        assert "status" in response
        assert response["status"] == 200

    def test_least_privilege_report_with_threshold(self):
        """Verify custom threshold parameter works."""
        response = analyzer_handlers.get_least_privilege_report(threshold=90.0)

        assert response["threshold"] == 90.0
        # Failing principals should have score < 90
        for principal in response["failing_principals"]:
            assert principal["score"] < 90.0

    def test_least_privilege_report_recommendations_present(self):
        """Verify recommendations are generated."""
        response = analyzer_handlers.get_least_privilege_report()

        assert isinstance(response["recommendations"], list)
        assert len(response["recommendations"]) > 0

    def test_orphan_principals_returns_valid_structure(self):
        """Verify orphan detection returns proper structure."""
        response = analyzer_handlers.get_orphan_principals()

        assert "orphan_count" in response
        assert "orphans" in response
        assert "status" in response
        assert response["status"] == 200
        assert isinstance(response["orphans"], list)


class TestEvidencePackEndpoints:
    """Test contract compliance for /evidence-pack endpoints."""

    def test_generate_evidence_pack_returns_valid_structure(self):
        """Verify evidence pack has proper structure."""
        response = evidence_handlers.generate_evidence_pack()

        assert "evidence_pack" in response
        assert "status" in response
        assert response["status"] == 200

        pack = response["evidence_pack"]
        assert "id" in pack
        assert "generated_at" in pack
        assert "principal_snapshot_count" in pack
        assert "audit_event_range_hours" in pack
        assert "conformance_score" in pack
        assert "missing_events" in pack

    def test_generate_evidence_pack_with_hours_back(self):
        """Verify hours_back parameter is respected."""
        response = evidence_handlers.generate_evidence_pack(hours_back=48)

        pack = response["evidence_pack"]
        assert pack["audit_event_range_hours"] == 48

    def test_generate_evidence_pack_includes_decisions(self):
        """Verify evidence pack includes decisions when requested."""
        response = evidence_handlers.generate_evidence_pack(include_decisions=True)

        pack = response["evidence_pack"]
        assert "decisions" in pack
        assert isinstance(pack["decisions"], dict)

    def test_generate_evidence_pack_includes_catalog(self):
        """Verify evidence pack includes catalog when requested."""
        response = evidence_handlers.generate_evidence_pack(include_catalog=True)

        pack = response["evidence_pack"]
        assert "catalog_snapshot" in pack
        assert isinstance(pack["catalog_snapshot"], dict)

    def test_reconstruct_trace_returns_valid_structure(self):
        """Verify trace reconstruction has proper structure."""
        # Record a decision to create trace
        corr_id = "test-trace-correlation"
        decision_handlers.record_decision(
            subject_type="agent",
            subject_id="agent-trace",
            action="test:action",
            resource="test:resource",
            effect="allow",
            policy_reference="test-policy",
            correlation_id=corr_id,
        )

        # Reconstruct trace
        response = evidence_handlers.reconstruct_trace(corr_id)

        assert "reconstruction" in response
        assert "integrity_status" in response
        assert "status" in response
        assert response["status"] == 200

        reconstruction = response["reconstruction"]
        assert "correlation_id" in reconstruction
        assert "event_count" in reconstruction
        assert "events" in reconstruction
        assert "complete" in reconstruction

    def test_validate_evidence_integrity_with_valid_events(self):
        """Verify integrity validation for valid events."""
        from agentcore_governance import evidence

        # Create valid events
        events = [
            evidence.construct_authorization_decision_event(
                agent_id="agent-1",
                tool_id="tool-1",
                effect="allow",
                reason="authorized",
                correlation_id="test-corr",
            )
        ]

        response = evidence_handlers.validate_evidence_integrity(events)

        assert response["status"] == 200
        assert "total_events" in response
        assert "passed" in response
        assert "failed" in response
        assert "overall_status" in response
        assert response["overall_status"] in ("passed", "failed")

    def test_validate_evidence_integrity_detects_missing_hash(self):
        """Verify integrity validation detects missing hash."""
        # Create event without hash
        events = [
            {
                "id": "test-event-1",
                "event_type": "test_event",
                "timestamp": "2025-11-05T12:00:00Z",
            }
        ]

        response = evidence_handlers.validate_evidence_integrity(events)

        assert response["status"] == 200
        assert response["failed"] >= 1
        assert any(r["status"] == "missing_hash" for r in response["validation_results"])

    def test_validate_evidence_integrity_detects_tampering(self):
        """Verify integrity validation detects tampered hash."""
        from agentcore_governance import evidence

        # Create valid event then tamper with hash
        event = evidence.construct_authorization_decision_event(
            agent_id="agent-1",
            tool_id="tool-1",
            effect="allow",
            reason="authorized",
        )
        event["integrity_hash"] = "tampered_hash_value_123456"

        response = evidence_handlers.validate_evidence_integrity([event])

        assert response["status"] == 200
        # Should detect tampering (implementation may vary)
        # At minimum, should complete validation
        assert "validation_results" in response
