"""Contract tests for authorization endpoints."""

from __future__ import annotations

from unittest.mock import patch

from agentcore_governance import authorization
from agentcore_governance.api import authorization_handlers


class TestGetAgentToolsEndpoint:
    """Contract tests for GET /authorization/agents/{agentId}/tools endpoint."""

    def setup_method(self):
        """Clear authorization store before each test."""
        authorization.clear_authorization_store()

    def test_response_schema_basic(self):
        """Test that response contains required fields."""
        response = authorization_handlers.get_agent_tools("test-agent")

        assert "agent_id" in response
        assert "authorized_tools" in response
        assert "total_count" in response
        assert isinstance(response["authorized_tools"], list)
        assert isinstance(response["total_count"], int)

    def test_empty_authorization_list(self):
        """Test response for agent with no authorized tools."""
        response = authorization_handlers.get_agent_tools("unknown-agent")

        assert response["agent_id"] == "unknown-agent"
        assert response["authorized_tools"] == []
        assert response["total_count"] == 0

    def test_populated_authorization_list(self):
        """Test response for agent with authorized tools."""
        authorization.set_authorized_tools("test-agent", ["tool1", "tool2", "tool3"])

        response = authorization_handlers.get_agent_tools("test-agent")

        assert response["agent_id"] == "test-agent"
        assert set(response["authorized_tools"]) == {"tool1", "tool2", "tool3"}
        assert response["total_count"] == 3

    def test_error_handling(self):
        """Test error handling returns proper error structure."""
        with patch(
            "agentcore_governance.authorization.get_authorized_tools",
            side_effect=Exception("Test error"),
        ):
            response = authorization_handlers.get_agent_tools("test-agent")

        assert "error" in response
        assert response["error"] == "Test error"
        assert response["authorized_tools"] == []


class TestUpdateAgentToolsEndpoint:
    """Contract tests for PUT /authorization/agents/{agentId}/tools endpoint."""

    def setup_method(self):
        """Clear authorization store before each test."""
        authorization.clear_authorization_store()

    def test_response_schema_success(self):
        """Test successful update response structure."""
        response = authorization_handlers.update_agent_tools(
            "test-agent",
            ["tool1", "tool2"],
            validate_classification=False,
        )

        assert "success" in response
        assert "agent_id" in response
        assert "authorized_tools" in response
        assert "total_count" in response
        assert "changes" in response
        assert "audit_events" in response
        assert "message" in response

    def test_changes_differential(self):
        """Test that changes show differential report."""
        response = authorization_handlers.update_agent_tools(
            "test-agent",
            ["tool1", "tool2"],
            validate_classification=False,
        )

        changes = response["changes"]
        assert "added" in changes
        assert "removed" in changes
        assert "unchanged" in changes
        assert set(changes["added"]) == {"tool1", "tool2"}

    def test_authorization_update_with_reason(self):
        """Test authorization update with justification."""
        response = authorization_handlers.update_agent_tools(
            "test-agent",
            ["tool1"],
            reason="Testing new tool",
            validate_classification=False,
        )

        assert response["success"] is True
        assert len(response["audit_events"]) == 1
        assert "Testing new tool" in response["audit_events"][0]["reason"]

    def test_adding_tools(self):
        """Test adding tools to existing authorization."""
        authorization.set_authorized_tools("test-agent", ["tool1"])

        response = authorization_handlers.update_agent_tools(
            "test-agent",
            ["tool1", "tool2", "tool3"],
            validate_classification=False,
        )

        assert response["success"] is True
        assert set(response["changes"]["added"]) == {"tool2", "tool3"}
        assert response["changes"]["unchanged"] == ["tool1"]
        assert response["changes"]["removed"] == []

    def test_removing_tools(self):
        """Test removing tools from authorization."""
        authorization.set_authorized_tools("test-agent", ["tool1", "tool2", "tool3"])

        response = authorization_handlers.update_agent_tools(
            "test-agent",
            ["tool1"],
            validate_classification=False,
        )

        assert response["success"] is True
        assert response["changes"]["added"] == []
        assert set(response["changes"]["removed"]) == {"tool2", "tool3"}
        assert response["changes"]["unchanged"] == ["tool1"]

    def test_audit_events_generated(self):
        """Test that audit events are generated for changes."""
        authorization.set_authorized_tools("test-agent", ["tool1"])

        response = authorization_handlers.update_agent_tools(
            "test-agent",
            ["tool2"],
            validate_classification=False,
        )

        audit_events = response["audit_events"]
        assert len(audit_events) == 2  # 1 added, 1 removed

        # Check added event
        added_events = [e for e in audit_events if e["effect"] == "allow"]
        assert len(added_events) == 1
        assert added_events[0]["tool_id"] == "tool2"

        # Check removed event
        removed_events = [e for e in audit_events if e["effect"] == "deny"]
        assert len(removed_events) == 1
        assert removed_events[0]["tool_id"] == "tool1"

    def test_classification_validation_failure(self):
        """Test that SENSITIVE tools without approval are rejected."""
        mock_registry = {
            "tools": [
                {
                    "id": "sensitive-tool",
                    "classification": "SENSITIVE",
                    "owner": "security-team",
                }
            ]
        }

        with patch(
            "agentcore_governance.classification.load_tool_classifications",
            return_value=mock_registry,
        ):
            response = authorization_handlers.update_agent_tools(
                "test-agent",
                ["sensitive-tool"],
                validate_classification=True,
            )

        assert response["success"] is False
        assert "validation_errors" in response
        assert len(response["validation_errors"]) == 1
        assert "requires approval" in response["validation_errors"][0]["reason"]

    def test_classification_validation_success_with_approval(self):
        """Test that SENSITIVE tools with approval are accepted."""
        mock_registry = {
            "tools": [
                {
                    "id": "sensitive-tool",
                    "classification": "SENSITIVE",
                    "owner": "security-team",
                }
            ]
        }

        approval_record = {
            "approved_by": "security-admin",
            "approved_at": "2024-11-01T00:00:00Z",
        }

        with patch(
            "agentcore_governance.classification.load_tool_classifications",
            return_value=mock_registry,
        ):
            response = authorization_handlers.update_agent_tools(
                "test-agent",
                ["sensitive-tool"],
                validate_classification=True,
                approval_records={"sensitive-tool": approval_record},
            )

        assert response["success"] is True
        assert response["authorized_tools"] == ["sensitive-tool"]

    def test_error_handling(self):
        """Test error handling returns proper error structure."""
        with patch(
            "agentcore_governance.authorization.set_authorized_tools",
            side_effect=Exception("Test error"),
        ):
            response = authorization_handlers.update_agent_tools(
                "test-agent",
                ["tool1"],
                validate_classification=False,
            )

        assert response["success"] is False
        assert "error" in response
        assert response["error"] == "Test error"


class TestCheckToolAccessEndpoint:
    """Tests for check_tool_access helper function."""

    def setup_method(self):
        """Clear authorization store before each test."""
        authorization.clear_authorization_store()

    def test_authorized_tool_access(self):
        """Test checking access for authorized tool."""
        authorization.set_authorized_tools("test-agent", ["tool1", "tool2"])

        response = authorization_handlers.check_tool_access("test-agent", "tool1")

        assert response["effect"] == "allow"
        assert response["authorized"] is True
        assert "audit_event" in response
        assert response["audit_event"]["effect"] == "allow"

    def test_unauthorized_tool_access(self):
        """Test checking access for unauthorized tool."""
        authorization.set_authorized_tools("test-agent", ["tool1"])

        response = authorization_handlers.check_tool_access("test-agent", "tool2")

        assert response["effect"] == "deny"
        assert response["authorized"] is False
        assert "NOT in authorized list" in response["reason"]

    def test_access_check_includes_classification(self):
        """Test that access check includes tool classification."""
        mock_registry = {
            "tools": [
                {
                    "id": "tool1",
                    "classification": "MODERATE",
                }
            ]
        }

        authorization.set_authorized_tools("test-agent", ["tool1"])

        with patch(
            "agentcore_governance.classification.get_tool_classification",
            return_value=mock_registry["tools"][0],
        ):
            response = authorization_handlers.check_tool_access("test-agent", "tool1")

        assert response["classification"] == "MODERATE"
