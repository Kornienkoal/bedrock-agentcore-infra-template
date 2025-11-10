"""Unit tests for classification loader."""

from unittest.mock import mock_open, patch

import pytest
import yaml
from agentcore_governance import classification


@pytest.fixture
def sample_registry_yaml():
    """Sample classification registry YAML."""
    return """
tools:
  - id: web_search
    classification: LOW
    owner: platform-team
    external_connectivity: INTERNET
    justification: Public web search for general queries
    review_interval_days: 90

  - id: customer_data_tool
    classification: SENSITIVE
    owner: customer-success
    external_connectivity: LIMITED
    justification: Accesses customer PII
    approval_reference: CHG-12345
    review_interval_days: 30
"""


class TestLoadToolClassifications:
    """Tests for load_tool_classifications."""

    def test_load_valid_registry(self, sample_registry_yaml):
        """Test loading a valid classification registry."""
        with (
            patch("builtins.open", mock_open(read_data=sample_registry_yaml)),
            patch("pathlib.Path.exists", return_value=True),
        ):
            registry = classification.load_tool_classifications()

        assert "tools" in registry
        assert len(registry["tools"]) == 2
        assert registry["tools"][0]["id"] == "web_search"
        assert registry["tools"][1]["classification"] == "SENSITIVE"

    def test_load_missing_registry(self):
        """Test loading when registry file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            registry = classification.load_tool_classifications()

        assert registry == {"tools": []}

    def test_load_invalid_yaml(self):
        """Test handling of malformed YAML."""
        invalid_yaml = "invalid: yaml: content: [unclosed"

        with (
            patch("builtins.open", mock_open(read_data=invalid_yaml)),
            patch("pathlib.Path.exists", return_value=True),
            pytest.raises(yaml.YAMLError),
        ):
            classification.load_tool_classifications()

    def test_load_invalid_structure(self):
        """Test handling of invalid registry structure."""
        invalid_registry = "tools: not_a_list"

        with (
            patch("builtins.open", mock_open(read_data=invalid_registry)),
            patch("pathlib.Path.exists", return_value=True),
            pytest.raises(ValueError, match="'tools' must be a list"),
        ):
            classification.load_tool_classifications()


class TestValidateToolEntry:
    """Tests for _validate_tool_entry."""

    def test_valid_tool_entry(self):
        """Test validation of a valid tool entry."""
        tool = {
            "id": "test_tool",
            "classification": "MODERATE",
            "owner": "team-a",
        }

        # Should not raise
        classification._validate_tool_entry(tool)

    def test_missing_required_field(self):
        """Test validation fails for missing required field."""
        tool = {
            "id": "test_tool",
            "classification": "LOW",
            # Missing 'owner'
        }

        with pytest.raises(ValueError, match="missing required field"):
            classification._validate_tool_entry(tool)

    def test_invalid_classification(self):
        """Test validation fails for invalid classification."""
        tool = {
            "id": "test_tool",
            "classification": "INVALID",
            "owner": "team-a",
        }

        with pytest.raises(ValueError, match="Invalid classification"):
            classification._validate_tool_entry(tool)


class TestGetToolClassification:
    """Tests for get_tool_classification."""

    def test_get_existing_tool(self):
        """Test retrieving an existing tool classification."""
        registry = {
            "tools": [
                {"id": "tool_a", "classification": "LOW", "owner": "team-1"},
                {"id": "tool_b", "classification": "SENSITIVE", "owner": "team-2"},
            ]
        }

        tool = classification.get_tool_classification("tool_b", registry)

        assert tool is not None
        assert tool["classification"] == "SENSITIVE"

    def test_get_nonexistent_tool(self):
        """Test retrieving a non-existent tool."""
        registry = {"tools": [{"id": "tool_a", "classification": "LOW", "owner": "team-1"}]}

        tool = classification.get_tool_classification("nonexistent", registry)

        assert tool is None


class TestRequiresApproval:
    """Tests for requires_approval."""

    def test_sensitive_tool_requires_approval(self):
        """Test that SENSITIVE tools require approval."""
        registry = {
            "tools": [{"id": "sensitive_tool", "classification": "SENSITIVE", "owner": "team-1"}]
        }

        assert classification.requires_approval("sensitive_tool", registry) is True

    def test_low_tool_no_approval(self):
        """Test that LOW tools don't require approval."""
        registry = {"tools": [{"id": "low_tool", "classification": "LOW", "owner": "team-1"}]}

        assert classification.requires_approval("low_tool", registry) is False

    def test_nonexistent_tool_no_approval(self):
        """Test that non-existent tools don't require approval."""
        registry = {"tools": []}

        assert classification.requires_approval("nonexistent", registry) is False
