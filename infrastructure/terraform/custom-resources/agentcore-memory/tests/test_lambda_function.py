"""Unit tests for memory custom resource Lambda function."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Add parent directory to path to import lambda_function
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def lambda_module():
    """Import Lambda function module with mocked dependencies."""
    import lambda_function

    return lambda_function


class TestCreateMemory:
    """Test CREATE operation."""

    def test_create_memory_success(
        self,
        lambda_module,
        create_event,
        lambda_context,
        mock_bedrock_memory_response,
    ):
        """Test successful memory creation."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_bedrock.create_memory.return_value = mock_bedrock_memory_response

        # Mock SSM client
        mock_ssm = MagicMock()

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(create_event, lambda_context)

        # Verify Bedrock create_memory called
        mock_bedrock.create_memory.assert_called_once()
        call_args = mock_bedrock.create_memory.call_args[1]
        assert call_args["name"] == "test-memory"
        assert "memoryStrategies" in call_args

        # Verify cfnresponse SUCCESS
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"
        assert args[3]["MemoryId"] == "test-memory-id-12345"

    def test_create_memory_with_multiple_strategies(
        self, lambda_module, create_event, lambda_context, mock_bedrock_memory_response
    ):
        """Test memory creation with multiple strategies."""
        mock_bedrock = MagicMock()
        mock_bedrock.create_memory.return_value = mock_bedrock_memory_response

        # Mock SSM client
        mock_ssm = MagicMock()

        # Patch the getter functions to return mocked clients
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send"),
        ):
            lambda_module.handler(create_event, lambda_context)

        # Verify strategies passed correctly (Lambda builds nested structure)
        call_args = mock_bedrock.create_memory.call_args[1]
        strategies = call_args["memoryStrategies"]
        assert len(strategies) == 2
        assert "userPreferenceMemoryStrategy" in strategies[0]
        assert "semanticMemoryStrategy" in strategies[1]

    def test_create_memory_bedrock_error(
        self, lambda_module, create_event, lambda_context
    ):
        """Test memory creation with Bedrock API error."""
        # Mock Bedrock client error
        mock_bedrock = MagicMock()
        mock_bedrock.create_memory.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Invalid memory config",
                }
            },
            "CreateMemory",
        )

        # Mock SSM client
        mock_ssm = MagicMock()

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(create_event, lambda_context)

        # Verify cfnresponse FAILED
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "FAILED"

    def test_create_memory_ssm_parameter_storage(
        self,
        lambda_module,
        create_event,
        lambda_context,
        mock_bedrock_memory_response,
    ):
        """Test SSM parameter creation during memory creation."""
        mock_bedrock = MagicMock()
        mock_bedrock.create_memory.return_value = mock_bedrock_memory_response

        mock_ssm = MagicMock()

        # Patch the getter functions to return mocked clients
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send"),
        ):
            lambda_module.handler(create_event, lambda_context)

        # Verify SSM parameter calls
        assert mock_ssm.put_parameter.call_count >= 1
        calls = mock_ssm.put_parameter.call_args_list

        # Check memory_id parameter
        memory_id_call = next((c for c in calls if "/memory/memory_id" in c[1]["Name"]), None)
        assert memory_id_call is not None
        assert memory_id_call[1]["Value"] == "test-memory-id-12345"
        assert memory_id_call[1]["Type"] == "String"


class TestUpdateMemory:
    """Test UPDATE operation."""

    def test_update_memory_success(
        self,
        lambda_module,
        update_event,
        lambda_context,
        mock_bedrock_memory_response,
    ):
        """Test successful memory update."""
        mock_bedrock = MagicMock()
        mock_bedrock.get_memory.return_value = mock_bedrock_memory_response
        mock_bedrock.update_memory.return_value = mock_bedrock_memory_response

        mock_ssm = MagicMock()

        # Patch the getter functions to return mocked clients
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(update_event, lambda_context)

        # Verify cfnresponse SUCCESS
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"

    def test_update_memory_strategy_changes(
        self, lambda_module, update_event, lambda_context, mock_bedrock_memory_response
    ):
        """Test update with changed memory strategies."""
        mock_bedrock = MagicMock()
        mock_bedrock.get_memory.return_value = mock_bedrock_memory_response
        mock_bedrock.update_memory.return_value = mock_bedrock_memory_response

        mock_ssm = MagicMock()

        # Patch the getter functions to return mocked clients
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(update_event, lambda_context)

        # Verify cfnresponse SUCCESS
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"


class TestDeleteMemory:
    """Test DELETE operation."""

    def test_delete_memory_success(self, lambda_module, delete_event, lambda_context):
        """Test successful memory deletion."""
        mock_bedrock = MagicMock()
        mock_bedrock.delete_memory.return_value = {}

        mock_ssm = MagicMock()

        # Patch the getter functions to return mocked clients
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(delete_event, lambda_context)

        # Verify Bedrock delete_memory called
        mock_bedrock.delete_memory.assert_called_once_with(memoryId="test-memory-id-12345")

        # Verify SSM parameters deleted
        assert mock_ssm.delete_parameter.call_count >= 1

        # Verify cfnresponse SUCCESS
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"

    def test_delete_memory_not_found(self, lambda_module, delete_event, lambda_context):
        """Test memory deletion when memory doesn't exist."""
        mock_bedrock = MagicMock()
        mock_bedrock.delete_memory.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Memory not found",
                }
            },
            "DeleteMemory",
        )

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_bedrock

            with patch("lambda_function.cfnresponse.send") as mock_cfn_send:
                lambda_module.handler(delete_event, lambda_context)

                # Should succeed even if memory not found (idempotent)
                mock_cfn_send.assert_called_once()
                args = mock_cfn_send.call_args[0]
                assert args[2] == "SUCCESS"


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_request_type(self, lambda_module, create_event, lambda_context):
        """Test handling of invalid RequestType."""
        create_event["RequestType"] = "Invalid"

        with patch("lambda_function.cfnresponse.send") as mock_cfn_send:
            lambda_module.handler(create_event, lambda_context)

            # Should send FAILED response
            mock_cfn_send.assert_called_once()
            args = mock_cfn_send.call_args[0]
            assert args[2] == "FAILED"

    def test_missing_required_properties(self, lambda_module, create_event, lambda_context):
        """Test handling of missing required properties."""
        del create_event["ResourceProperties"]["MemoryName"]

        with patch("lambda_function.cfnresponse.send") as mock_cfn_send:
            lambda_module.handler(create_event, lambda_context)

            # Should send FAILED response
            mock_cfn_send.assert_called_once()
            args = mock_cfn_send.call_args[0]
            assert args[2] == "FAILED"

    def test_invalid_memory_strategy(self, lambda_module, create_event, lambda_context):
        """Test handling of invalid memory strategy type."""
        create_event["ResourceProperties"]["MemoryStrategies"] = [
            {"type": "invalidStrategy", "maxRecords": 1000}
        ]

        mock_bedrock = MagicMock()
        mock_bedrock.create_memory.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Invalid strategy type",
                }
            },
            "CreateMemory",
        )

        mock_ssm = MagicMock()

        # Patch the getter functions to return mocked clients
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(create_event, lambda_context)

        # Should send FAILED response
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "FAILED"
