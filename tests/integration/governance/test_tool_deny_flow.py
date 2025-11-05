"""Integration test for tool invocation denial flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agentcore_governance import authorization
from agentcore_governance.api import authorization_handlers


class TestToolDenyFlow:
    """Integration tests for tool access denial scenarios."""

    def setup_method(self):
        """Clear authorization store before each test."""
        authorization.clear_authorization_store()

    def test_remove_tool_then_deny_invocation(self):
        """Test independent criterion: Remove tool via PUT → subsequent invocation denied."""
        agent_id = "test-agent"
        authorized_tool = "tool1"
        unauthorized_tool = "tool2"

        # Step 1: Set up initial authorization with both tools
        authorization.set_authorized_tools(agent_id, [authorized_tool, unauthorized_tool])

        # Verify both tools are initially authorized
        check1 = authorization_handlers.check_tool_access(agent_id, authorized_tool)
        check2 = authorization_handlers.check_tool_access(agent_id, unauthorized_tool)

        assert check1["effect"] == "allow"
        assert check2["effect"] == "allow"

        # Step 2: Remove tool2 via PUT endpoint
        update_response = authorization_handlers.update_agent_tools(
            agent_id,
            [authorized_tool],  # Only tool1 remains
            reason="Removing tool2 for security reasons",
            validate_classification=False,
        )

        # Verify update was successful
        assert update_response["success"] is True
        assert unauthorized_tool in update_response["changes"]["removed"]
        assert update_response["total_count"] == 1

        # Step 3: Simulate subsequent invocation of removed tool
        deny_check = authorization_handlers.check_tool_access(agent_id, unauthorized_tool)

        # Verify denial
        assert deny_check["effect"] == "deny"
        assert deny_check["authorized"] is False
        assert "NOT in authorized list" in deny_check["reason"]

        # Step 4: Verify audit event was created for denial
        audit_event = deny_check["audit_event"]
        assert audit_event["event_type"] == "authorization_decision"
        assert audit_event["effect"] == "deny"
        assert audit_event["tool_id"] == unauthorized_tool
        assert audit_event["agent_id"] == agent_id
        assert "integrity_hash" in audit_event

        # Step 5: Verify authorized tool still works
        allow_check = authorization_handlers.check_tool_access(agent_id, authorized_tool)
        assert allow_check["effect"] == "allow"

    def test_unauthorized_tool_never_added(self):
        """Test that tools never added to authorization are denied."""
        agent_id = "new-agent"
        tool_id = "never-authorized-tool"

        # Attempt to access tool that was never authorized
        check = authorization_handlers.check_tool_access(agent_id, tool_id)

        assert check["effect"] == "deny"
        assert check["authorized"] is False
        assert tool_id in check["reason"]

    def test_empty_authorization_denies_all(self):
        """Test that agent with empty authorization cannot access any tools."""
        agent_id = "restricted-agent"
        authorization.set_authorized_tools(agent_id, [])

        # Try to access various tools
        for tool_id in ["tool1", "tool2", "tool3"]:
            check = authorization_handlers.check_tool_access(agent_id, tool_id)
            assert check["effect"] == "deny"
            assert check["authorized"] is False

    def test_audit_trail_for_denial(self):
        """Test that denied invocations create complete audit trail."""
        agent_id = "audited-agent"
        denied_tool = "blocked-tool"

        # Set up authorization without the tool
        authorization.set_authorized_tools(agent_id, ["other-tool"])

        # Attempt access
        correlation_id = "test-correlation-123"
        check = authorization_handlers.check_tool_access(
            agent_id,
            denied_tool,
            correlation_id=correlation_id,
        )

        # Verify audit event structure
        audit_event = check["audit_event"]
        assert audit_event["correlation_id"] == correlation_id
        assert audit_event["agent_id"] == agent_id
        assert audit_event["tool_id"] == denied_tool
        assert audit_event["effect"] == "deny"
        assert audit_event["id"]  # Has unique ID
        assert audit_event["timestamp"]  # Has timestamp

    def test_classification_enforcement_denies_sensitive_without_approval(self):
        """Test that SENSITIVE tools are denied without proper approval."""
        mock_registry = {
            "tools": [
                {
                    "id": "sensitive-db-access",
                    "classification": "SENSITIVE",
                    "owner": "security-team",
                }
            ]
        }

        agent_id = "test-agent"
        sensitive_tool = "sensitive-db-access"

        # Try to authorize SENSITIVE tool without approval
        with patch("agentcore_governance.classification.load_tool_classifications", return_value=mock_registry):
            response = authorization_handlers.update_agent_tools(
                agent_id,
                [sensitive_tool],
                validate_classification=True,
            )

        # Verify authorization was denied
        assert response["success"] is False
        assert "validation_errors" in response
        assert any("requires approval" in err["reason"] for err in response["validation_errors"])

        # Verify tool is not in authorization list
        tools = authorization.get_authorized_tools(agent_id)
        assert sensitive_tool not in tools

        # Verify invocation would be denied
        check = authorization_handlers.check_tool_access(agent_id, sensitive_tool)
        assert check["effect"] == "deny"

    def test_multiple_tools_removed_all_denied(self):
        """Test removing multiple tools denies all of them."""
        agent_id = "multi-tool-agent"
        initial_tools = ["tool1", "tool2", "tool3", "tool4"]
        remaining_tools = ["tool1"]

        # Set up with 4 tools
        authorization.set_authorized_tools(agent_id, initial_tools)

        # Remove 3 tools
        update_response = authorization_handlers.update_agent_tools(
            agent_id,
            remaining_tools,
            reason="Security audit cleanup",
            validate_classification=False,
        )

        # Verify removed tools are denied
        removed_tools = update_response["changes"]["removed"]
        assert len(removed_tools) == 3

        for tool_id in removed_tools:
            check = authorization_handlers.check_tool_access(agent_id, tool_id)
            assert check["effect"] == "deny"
            assert check["authorized"] is False

        # Verify remaining tool is still allowed
        check = authorization_handlers.check_tool_access(agent_id, "tool1")
        assert check["effect"] == "allow"

    def test_differential_report_tracks_removals(self):
        """Test that differential report accurately tracks tool removals."""
        agent_id = "tracked-agent"

        # Initial authorization
        authorization.set_authorized_tools(agent_id, ["tool1", "tool2", "tool3"])

        # Remove tool2
        update1 = authorization_handlers.update_agent_tools(
            agent_id,
            ["tool1", "tool3"],
            validate_classification=False,
        )

        assert "tool2" in update1["changes"]["removed"]

        # Remove tool3
        update2 = authorization_handlers.update_agent_tools(
            agent_id,
            ["tool1"],
            validate_classification=False,
        )

        assert "tool3" in update2["changes"]["removed"]

        # Generate full differential report
        diff_report = authorization.generate_differential_report(agent_id)

        assert diff_report["agent_id"] == agent_id
        assert diff_report["current_tools"] == ["tool1"]
        assert diff_report["total_changes"] == 3  # Initial + 2 updates
