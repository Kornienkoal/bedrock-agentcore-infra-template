"""Unit tests for catalog aggregation."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from agentcore_governance import catalog


@pytest.fixture
def mock_iam_client():
    """Mock IAM client for testing."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_roles():
    """Sample IAM roles for testing."""
    return {
        "Roles": [
            {
                "RoleName": "agentcore-dev-execution-role",
                "Arn": "arn:aws:iam::123456789012:role/agentcore-dev-execution-role",
                "CreateDate": datetime(2024, 1, 1, tzinfo=UTC),
                "Description": "Execution role for AgentCore runtime",
                "RoleLastUsed": {
                    "LastUsedDate": datetime(2024, 11, 1, tzinfo=UTC),
                },
            },
        ]
    }


@pytest.fixture
def sample_tags():
    """Sample IAM role tags."""
    return {
        "Tags": [
            {"Key": "Environment", "Value": "dev"},
            {"Key": "Owner", "Value": "platform-team"},
            {"Key": "Purpose", "Value": "Agent runtime execution"},
        ]
    }


class TestFetchPrincipalCatalog:
    """Tests for fetch_principal_catalog."""

    @patch("agentcore_governance.catalog.boto3")
    def test_fetch_principals_success(self, mock_boto, mock_iam_client, sample_roles, sample_tags):
        """Test successful principal catalog fetch."""
        mock_boto.client.return_value = mock_iam_client
        mock_iam_client.get_paginator.return_value.paginate.return_value = [sample_roles]
        mock_iam_client.list_role_tags.return_value = sample_tags
        mock_iam_client.list_attached_role_policies.return_value = {"AttachedPolicies": []}

        principals = catalog.fetch_principal_catalog()

        assert len(principals) == 1
        assert principals[0]["id"] == "arn:aws:iam::123456789012:role/agentcore-dev-execution-role"
        assert principals[0]["environment"] == "dev"
        assert principals[0]["owner"] == "platform-team"
        assert principals[0]["type"] == "execution_role"

    @patch("agentcore_governance.catalog.boto3")
    def test_fetch_principals_with_environment_filter(
        self, mock_boto, mock_iam_client, sample_roles, sample_tags
    ):
        """Test catalog fetch with environment filter."""
        mock_boto.client.return_value = mock_iam_client
        mock_iam_client.get_paginator.return_value.paginate.return_value = [sample_roles]
        mock_iam_client.list_role_tags.return_value = sample_tags
        mock_iam_client.list_attached_role_policies.return_value = {"AttachedPolicies": []}

        principals = catalog.fetch_principal_catalog(environments=["dev"])
        assert len(principals) == 1

        principals = catalog.fetch_principal_catalog(environments=["prod"])
        assert len(principals) == 0


class TestSummarizePolicyFootprint:
    """Tests for summarize_policy_footprint."""

    def test_summarize_with_wildcards(self):
        """Test policy footprint with wildcard actions."""
        policies = [
            {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:*", "dynamodb:GetItem"],
                        "Resource": "*",
                    }
                ]
            }
        ]

        footprint = catalog.summarize_policy_footprint(policies)

        assert footprint["action_count"] == 2
        assert "s3:*" in footprint["wildcard_actions"]
        assert footprint["resource_scope_wideness"] == "BROAD"

    def test_summarize_narrow_scope(self):
        """Test policy footprint with narrow resource scope."""
        policies = [
            {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:GetObject",
                        "Resource": "arn:aws:s3:::my-bucket/*",
                    }
                ]
            }
        ]

        footprint = catalog.summarize_policy_footprint(policies)

        assert footprint["resource_scope_wideness"] == "NARROW"
        assert footprint["wildcard_actions"] == []


class TestFlagInactivePrincipals:
    """Tests for flag_inactive_principals."""

    def test_flag_inactive_principals(self):
        """Test inactivity flagging."""
        old_date = (
            datetime.now(UTC).replace(tzinfo=None) - __import__("datetime").timedelta(days=45)
        ).isoformat() + "Z"
        recent_date = (
            datetime.now(UTC).replace(tzinfo=None) - __import__("datetime").timedelta(days=10)
        ).isoformat() + "Z"

        principals = [
            {"id": "old-role", "last_used_at": old_date},
            {"id": "recent-role", "last_used_at": recent_date},
            {"id": "never-used-role", "last_used_at": None},
        ]

        flagged = catalog.flag_inactive_principals(principals, inactivity_days=30)

        assert flagged[0]["inactive"] is True
        assert flagged[1]["inactive"] is False
        assert flagged[2]["inactive"] is True
