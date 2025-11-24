"""Shared pytest fixtures for all custom resource tests."""

import os

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(scope="session", autouse=True)
def aws_credentials():
    """Mock AWS credentials for moto (session-wide)."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture
def lambda_context():
    """Mock Lambda context object (generic)."""

    class MockContext:
        function_name = "custom-resource-provisioner"
        function_version = "$LATEST"
        invoked_function_arn = (
            "arn:aws:lambda:us-east-1:123456789012:function:custom-resource-provisioner"
        )
        memory_limit_in_mb = 256
        aws_request_id = "test-request-id"
        log_group_name = "/aws/lambda/custom-resource-provisioner"
        log_stream_name = "2025/01/01/[$LATEST]test-stream"

        @staticmethod
        def get_remaining_time_in_millis():
            return 60000

    return MockContext()


@pytest.fixture
def ssm_client(aws_credentials):
    """Mock SSM client."""
    _ = aws_credentials
    with mock_aws():
        yield boto3.client("ssm", region_name="us-east-1")


@pytest.fixture
def iam_client(aws_credentials):
    """Mock IAM client."""
    _ = aws_credentials
    with mock_aws():
        yield boto3.client("iam", region_name="us-east-1")
