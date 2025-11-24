"""Unit tests for gateway custom resource Lambda function."""

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


class TestCreateGateway:
    """Test CREATE operation."""

    def test_create_gateway_success(
        self,
        lambda_module,
        create_event,
        lambda_context,
        mock_bedrock_response,
    ):
        """Test successful gateway creation."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_bedrock.create_gateway.return_value = mock_bedrock_response
        # Mock get_gateway to return ACTIVE status immediately (no polling delay)
        mock_bedrock.get_gateway.return_value = {
            **mock_bedrock_response,
            "status": "ACTIVE",
            "gatewayUrl": "https://test-gateway-id-12345.bedrock-gateway.us-east-1.amazonaws.com",
        }

        # Mock SSM client
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-pool-id"}}

        # Patch the getter functions to return mocked clients
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
            patch("time.sleep"),
        ):
            lambda_module.handler(create_event, lambda_context)

        # Verify Bedrock create_gateway called
        mock_bedrock.create_gateway.assert_called_once()
        call_args = mock_bedrock.create_gateway.call_args[1]
        assert call_args["name"] == "test-gateway"
        assert "roleArn" in call_args

        # Verify cfnresponse SUCCESS
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"
        assert args[3]["GatewayId"] == "test-gateway-id-12345"

    def test_create_gateway_bedrock_error(
        self, lambda_module, create_event, lambda_context
    ):
        """Test gateway creation with Bedrock API error."""
        # Mock Bedrock client error
        mock_bedrock = MagicMock()
        mock_bedrock.create_gateway.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid role ARN"}},
            "CreateGateway",
        )

        # Mock SSM client
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-pool-id"}}

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

    def test_create_gateway_ssm_parameter_storage(
        self,
        lambda_module,
        create_event,
        lambda_context,
        mock_bedrock_response,
    ):
        """Test SSM parameter creation during gateway creation."""
        mock_bedrock = MagicMock()
        mock_bedrock.create_gateway.return_value = mock_bedrock_response
        mock_bedrock.get_gateway.return_value = {
            **mock_bedrock_response,
            "status": "ACTIVE",
            "gatewayUrl": "https://test-gateway-id-12345.bedrock-gateway.us-east-1.amazonaws.com",
        }

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = [  # For Cognito config lookup
            {"Parameter": {"Value": "test-pool-id"}},
            {"Parameter": {"Value": "test-client-id"}},
        ] + [
            ClientError({"Error": {"Code": "ParameterNotFound"}}, "GetParameter")
        ] * 10  # For SSM puts (param doesn't exist)

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send"),
            patch("time.sleep"),
        ):
            lambda_module.handler(create_event, lambda_context)

        # Verify SSM parameter calls
        assert mock_ssm.put_parameter.call_count >= 1
        calls = mock_ssm.put_parameter.call_args_list

        # Check gateway_id parameter
        gateway_id_call = next(
            (c for c in calls if "/gateway/gateway_id" in c[1]["Name"]),
            None,
        )
        assert gateway_id_call is not None
        assert gateway_id_call[1]["Value"] == "test-gateway-id-12345"
        assert gateway_id_call[1]["Type"] == "String"


class TestUpdateGateway:
    """Test UPDATE operation."""

    def test_update_gateway_success(
        self,
        lambda_module,
        update_event,
        lambda_context,
        mock_bedrock_response,
    ):
        """Test successful gateway update."""
        mock_bedrock = MagicMock()
        mock_bedrock.update_gateway.return_value = mock_bedrock_response
        mock_bedrock.get_gateway.return_value = {
            **mock_bedrock_response,
            "status": "ACTIVE",
        }

        # Mock SSM client
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-pool-id"}}

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
            patch("time.sleep"),
        ):
            lambda_module.handler(update_event, lambda_context)

        # Verify Bedrock update_gateway called
        mock_bedrock.update_gateway.assert_called_once()
        call_args = mock_bedrock.update_gateway.call_args[1]
        assert call_args["gatewayIdentifier"] == "test-gateway-id-12345"

        # Verify cfnresponse SUCCESS
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"

    def test_update_gateway_idempotent(
        self, lambda_module, update_event, lambda_context, mock_bedrock_response
    ):
        """Test update is idempotent when properties unchanged."""
        # Make properties identical
        update_event["ResourceProperties"] = update_event["OldResourceProperties"].copy()

        mock_bedrock = MagicMock()
        mock_bedrock.get_gateway.return_value = {
            **mock_bedrock_response,
            "status": "ACTIVE",
        }

        # Mock SSM client
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-pool-id"}}

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(update_event, lambda_context)

        # Should skip update if properties unchanged
        # (implementation detail - may call get_gateway to verify)
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"


class TestDeleteGateway:
    """Test DELETE operation."""

    def test_delete_gateway_success(self, lambda_module, delete_event, lambda_context):
        """Test successful gateway deletion."""
        mock_bedrock = MagicMock()
        mock_bedrock.delete_gateway.return_value = {}

        mock_ssm = MagicMock()

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(delete_event, lambda_context)

        # Verify Bedrock delete_gateway called
        mock_bedrock.delete_gateway.assert_called_once_with(gatewayId="test-gateway-id-12345")

        # Verify SSM parameters deleted
        assert mock_ssm.delete_parameter.call_count >= 1

        # Verify cfnresponse SUCCESS
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"

    def test_delete_gateway_not_found(self, lambda_module, delete_event, lambda_context):
        """Test gateway deletion when gateway doesn't exist."""
        mock_bedrock = MagicMock()
        mock_bedrock.delete_gateway.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Gateway not found",
                }
            },
            "DeleteGateway",
        )

        # Mock SSM client
        mock_ssm = MagicMock()

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
        ):
            lambda_module.handler(delete_event, lambda_context)

        # Should succeed even if gateway not found (idempotent)
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_request_type(self, lambda_module, create_event, lambda_context):
        """Test handling of invalid RequestType."""
        create_event["RequestType"] = "Invalid"

        # Mock clients (even though we won't reach them)
        mock_bedrock = MagicMock()
        mock_ssm = MagicMock()

        # Patch the module-level clients directly
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

    def test_missing_required_properties(self, lambda_module, create_event, lambda_context):
        """Test handling of missing required properties."""
        del create_event["ResourceProperties"]["GatewayName"]

        # Mock clients (even though we won't reach them)
        mock_bedrock = MagicMock()
        mock_ssm = MagicMock()

        # Patch the module-level clients directly
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

    def test_ssm_parameter_error_handling(
        self, lambda_module, create_event, lambda_context, mock_bedrock_response
    ):
        """Test handling of SSM parameter storage errors."""
        mock_bedrock = MagicMock()
        mock_bedrock.create_gateway.return_value = mock_bedrock_response
        mock_bedrock.get_gateway.return_value = {
            **mock_bedrock_response,
            "status": "ACTIVE",
            "gatewayUrl": "https://test-gateway-id-12345.bedrock-gateway.us-east-1.amazonaws.com",
        }

        mock_ssm = MagicMock()
        # First calls for Cognito config lookup succeed
        mock_ssm.get_parameter.side_effect = [
            {"Parameter": {"Value": "test-pool-id"}},
            {"Parameter": {"Value": "test-client-id"}},
            # Then subsequent calls for checking parameter existence fail
            ClientError({"Error": {"Code": "ParameterNotFound"}}, "GetParameter"),
            ClientError({"Error": {"Code": "ParameterNotFound"}}, "GetParameter"),
            ClientError({"Error": {"Code": "ParameterNotFound"}}, "GetParameter"),
            ClientError({"Error": {"Code": "ParameterNotFound"}}, "GetParameter"),
        ]
        # Fail on parameter storage
        mock_ssm.put_parameter.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ParameterLimitExceeded",
                    "Message": "Too many parameters",
                }
            },
            "PutParameter",
        )

        # Patch the module-level clients directly
        with (
            patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
            patch.object(lambda_module, "get_ssm_client", return_value=mock_ssm),
            patch("lambda_function.cfnresponse.send") as mock_cfn_send,
            patch("time.sleep"),
        ):
            lambda_module.handler(create_event, lambda_context)

        # Should send FAILED if SSM fails
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "FAILED"
