"""Unit tests for gateway targets custom resource Lambda function."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path to import lambda_function
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def lambda_module():
    import lambda_function

    return lambda_function


def test_create_targets_success(lambda_module, create_event, lambda_context, ssm_client):
    """Test successful creation of two targets when none exist."""
    mock_bedrock = MagicMock()
    # list -> empty
    mock_bedrock.get_paginator.return_value.paginate.return_value = [{"items": []}]
    # create returns ids
    mock_bedrock.create_gateway_target.side_effect = [
        {"targetId": "t-1"},
        {"targetId": "t-2"},
    ]

    with (
        patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
        patch.object(lambda_module, "get_ssm_client", return_value=ssm_client),
        patch("lambda_function.cfnresponse.send") as mock_cfn_send,
    ):
        lambda_module.handler(create_event, lambda_context)

        # Two creates
        assert mock_bedrock.create_gateway_target.call_count == 2

        first_call_kwargs = mock_bedrock.create_gateway_target.call_args_list[0][1]
        assert first_call_kwargs["credentialProviderConfigurations"] == [
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ]
        schema_payload = first_call_kwargs["targetConfiguration"]["mcp"]["lambda"][
            "toolSchema"
        ]
        assert "inlinePayload" in schema_payload
        assert schema_payload["inlinePayload"][0]["name"] == "check-warranty-status"

        # SUCCESS response
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"
        assert args[3]["Created"] == 2


def test_update_targets_change(lambda_module, update_event, lambda_context, ssm_client):
    """Test update path when lambdaArn changes."""
    mock_bedrock = MagicMock()
    # list -> existing targets with old lambdaArn
    mock_bedrock.get_paginator.return_value.paginate.return_value = [
        {
            "items": [
                {
                    "name": "check-warranty",
                    "targetId": "t-1",
                },
                {
                    "name": "web-search",
                    "targetId": "t-2",
                },
            ]
        }
    ]

    mock_bedrock.get_gateway_target.side_effect = [
        {
            "targetConfiguration": {
                "mcp": {
                    "lambda": {
                        "lambdaArn": "old-arn",
                        "toolSchema": {
                            "inlinePayload": [
                                {
                                    "name": "check_warranty_status",
                                    "description": "Old",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {"product_id": {"type": "string"}},
                                        "required": ["product_id"],
                                    },
                                }
                            ]
                        },
                    }
                }
            },
            "credentialProviderConfigurations": [{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        },
        {
            "targetConfiguration": {
                "mcp": {
                    "lambda": {
                        "lambdaArn": "old-arn",
                        "toolSchema": {
                            "inlinePayload": [
                                {
                                    "name": "web_search",
                                    "description": "Old",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {"query": {"type": "string"}},
                                        "required": ["query"],
                                    },
                                }
                            ]
                        },
                    }
                }
            },
            "credentialProviderConfigurations": [{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        },
    ]

    with (
        patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
        patch.object(lambda_module, "get_ssm_client", return_value=ssm_client),
        patch("lambda_function.cfnresponse.send") as mock_cfn_send,
    ):
        lambda_module.handler(update_event, lambda_context)

        assert mock_bedrock.update_gateway_target.call_count == 2
        first_update_kwargs = mock_bedrock.update_gateway_target.call_args_list[0][1]
        assert first_update_kwargs["targetId"] == "t-1"
        assert first_update_kwargs["credentialProviderConfigurations"] == [
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ]
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"
        assert args[3]["Updated"] == 2


def test_delete_targets_success(lambda_module, delete_event, lambda_context, ssm_client):
    """Test deletion of targets by name."""
    mock_bedrock = MagicMock()
    # list -> existing
    mock_bedrock.get_paginator.return_value.paginate.return_value = [
        {
            "items": [
                {"name": "check-warranty", "targetId": "t-1"},
                {"name": "web-search", "targetId": "t-2"},
            ]
        }
    ]

    with (
        patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
        patch.object(lambda_module, "get_ssm_client", return_value=ssm_client),
        patch("lambda_function.cfnresponse.send") as mock_cfn_send,
    ):
        lambda_module.handler(delete_event, lambda_context)

        assert mock_bedrock.delete_gateway_target.call_count == 2
        first_delete_kwargs = mock_bedrock.delete_gateway_target.call_args_list[0][1]
        assert first_delete_kwargs["targetId"] == "t-1"
        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "SUCCESS"
        assert args[3]["Deleted"] == 2


def test_invalid_request_type(lambda_module, create_event, lambda_context, ssm_client):
    """Test handling invalid RequestType."""
    create_event["RequestType"] = "Invalid"

    mock_bedrock = MagicMock()

    with (
        patch.object(lambda_module, "get_control_client", return_value=mock_bedrock),
        patch.object(lambda_module, "get_ssm_client", return_value=ssm_client),
        patch("lambda_function.cfnresponse.send") as mock_cfn_send,
    ):
        lambda_module.handler(create_event, lambda_context)

        mock_cfn_send.assert_called_once()
        args = mock_cfn_send.call_args[0]
        assert args[2] == "FAILED"
