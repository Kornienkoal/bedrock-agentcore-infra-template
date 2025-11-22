import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock environment variables
os.environ["COGNITO_USER_POOL_ID"] = "us-east-1_xxxxxx"
os.environ["COGNITO_CLIENT_ID"] = "client-id"
os.environ["AWS_REGION"] = "us-east-1"

# Mock boto3 and auth BEFORE importing lambda_function
# This prevents the top-level code from running with real boto3
mock_boto3 = MagicMock()
mock_auth_module = MagicMock()

# Add service directory to path so we can import lambda_function
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../services/frontend-gateway")
    )
)

# We need to patch sys.modules so that when lambda_function imports boto3 and auth, it gets our mocks
with patch.dict("sys.modules", {"boto3": mock_boto3, "auth": mock_auth_module}):
    import lambda_function


@pytest.fixture
def setup_mocks():
    # Reset mocks
    mock_boto3.reset_mock()
    mock_auth_module.reset_mock()

    # Setup default behavior for boto3 client creation
    mock_control = MagicMock()
    mock_runtime = MagicMock()

    def client_side_effect(service, **kwargs):  # noqa: ARG001
        if service == "bedrock-agentcore-control":
            return mock_control
        if service == "bedrock-agentcore":
            return mock_runtime
        return MagicMock()

    mock_boto3.client.side_effect = client_side_effect

    return mock_control, mock_runtime


def test_list_agents_authorized(setup_mocks):
    mock_control, _ = setup_mocks

    # Setup Auth
    # validate_token returns the claims dict directly
    mock_auth_module.validate_token.return_value = {
        "sub": "user123",
        "custom:allowed_agents": '["agent1"]',
    }

    # Setup Boto3 response
    mock_control.list_agent_runtimes.return_value = {
        "agentRuntimes": [
            {"agentRuntimeName": "agent1", "agentRuntimeArn": "arn:agent1"},
            {"agentRuntimeName": "agent2", "agentRuntimeArn": "arn:agent2"},
        ]
    }

    # Inject mocks into the module's global variables
    # We need to do this because the module was imported once, and the global variables
    # (control_client, runtime_client) were initialized then (using the mock_boto3 at that time).
    # However, to be safe and ensure test isolation, we explicitly set them here.
    lambda_function.control_client = mock_control
    lambda_function.runtime_client = MagicMock()

    event = {
        "rawPath": "/agents",
        "requestContext": {"http": {"method": "GET"}},
        "headers": {"authorization": "Bearer token"},
    }

    response = lambda_function.lambda_handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["agents"]) == 1
    assert body["agents"][0]["id"] == "agent1"


def test_invoke_agent_authorized(setup_mocks):
    mock_control, mock_runtime = setup_mocks

    mock_auth_module.validate_token.return_value = {
        "sub": "user123",
        "custom:allowed_agents": '["agent1"]',
    }

    mock_control.list_agent_runtimes.return_value = {
        "agentRuntimes": [{"agentRuntimeName": "agent1", "agentRuntimeArn": "arn:agent1"}]
    }

    mock_response_stream = MagicMock()
    mock_response_stream.read.return_value = b'"Hello"'
    mock_runtime.invoke_agent_runtime.return_value = {"response": mock_response_stream}

    lambda_function.control_client = mock_control
    lambda_function.runtime_client = mock_runtime

    event = {
        "rawPath": "/agents/agent1/invoke",
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"authorization": "Bearer token"},
        "body": json.dumps({"message": "Hi", "sessionId": "sess1"}),
    }

    response = lambda_function.lambda_handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["output"] == "Hello"


def test_invoke_agent_forbidden(setup_mocks):
    mock_control, mock_runtime = setup_mocks

    mock_auth_module.validate_token.return_value = {
        "sub": "user123",
        "custom:allowed_agents": '["agent1"]',
    }

    lambda_function.control_client = mock_control
    lambda_function.runtime_client = mock_runtime

    event = {
        "rawPath": "/agents/agent2/invoke",
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"authorization": "Bearer token"},
        "body": json.dumps({"message": "Hi", "sessionId": "sess1"}),
    }

    response = lambda_function.lambda_handler(event, None)

    assert response["statusCode"] == 403
