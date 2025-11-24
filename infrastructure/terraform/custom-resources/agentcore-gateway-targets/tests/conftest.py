"""Pytest fixtures for gateway targets custom resource tests.

Module-specific fixtures. Shared fixtures (aws_credentials, lambda_context, ssm_client)
are available from ../conftest.py
"""

from typing import Any

import boto3
import pytest
from moto import mock_aws


# Override ssm_client to seed gateway ID parameter
@pytest.fixture
def ssm_client(aws_credentials):
    """Mock SSM client with seeded gateway ID."""
    _ = aws_credentials
    with mock_aws():
        client = boto3.client("ssm", region_name="us-east-1")
        # Seed a gateway ID parameter
        client.put_parameter(
            Name="/agentcore/dev/gateway/gateway_id", Value="gw-123", Type="String"
        )
        yield client


@pytest.fixture
def create_event() -> dict[str, Any]:
    return {
        "RequestType": "Create",
        "ResponseURL": "",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/guid",
        "RequestId": "test-request-id-create",
        "LogicalResourceId": "GatewayTargets",
        "ResourceType": "Custom::GatewayTargets",
        "ResourceProperties": {
            "Environment": "dev",
            "AgentNamespace": "agentcore",
            "SSMPrefix": "/agentcore/dev/gateway",
            "Tools": [
                {
                    "name": "check-warranty",
                    "lambdaArn": "arn:aws:lambda:us-east-1:123456789012:function:agentcore-check-warranty-tool-dev",
                    "schema": {
                        "name": "check-warranty-status",
                        "description": "Check warranty status for a product.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "user_id": {"type": "string"},
                            },
                            "required": ["product_id"],
                        },
                    },
                },
                {
                    "name": "web-search",
                    "lambdaArn": "arn:aws:lambda:us-east-1:123456789012:function:agentcore-web-search-tool-dev",
                    "schema": {
                        "name": "web-search",
                        "description": "Search the web for information.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "max_results": {"type": "integer"},
                            },
                            "required": ["query"],
                        },
                    },
                },
            ],
        },
    }


@pytest.fixture
def update_event(create_event) -> dict[str, Any]:
    event = create_event.copy()
    event.update({"RequestType": "Update", "RequestId": "test-request-id-update"})
    return event


@pytest.fixture
def delete_event(create_event) -> dict[str, Any]:
    event = create_event.copy()
    event.update({"RequestType": "Delete", "RequestId": "test-request-id-delete"})
    return event
