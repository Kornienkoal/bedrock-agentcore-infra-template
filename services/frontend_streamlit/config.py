"""Configuration loader for Streamlit app.

Fetches Cognito and API Gateway configuration from AWS SSM Parameter Store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError


@dataclass
class CognitoConfig:
    """Cognito authentication configuration."""

    pool_id: str
    client_id: str
    client_secret: str
    domain: str
    region: str

    @property
    def authorize_url(self) -> str:
        """OAuth2 authorization endpoint."""
        return f"https://{self.domain}.auth.{self.region}.amazoncognito.com/oauth2/authorize"

    @property
    def token_url(self) -> str:
        """OAuth2 token endpoint."""
        return f"https://{self.domain}.auth.{self.region}.amazoncognito.com/oauth2/token"

    @property
    def logout_url(self) -> str:
        """Cognito logout endpoint."""
        return f"https://{self.domain}.auth.{self.region}.amazoncognito.com/logout"


@dataclass
class GatewayConfig:
    """API Gateway configuration."""

    invoke_url: str


@dataclass
class AppConfig:
    """Complete application configuration."""

    cognito: CognitoConfig
    gateway: GatewayConfig
    frontend_gateway_url: str
    environment: str


def get_ssm_parameter(parameter_name: str, with_decryption: bool = False) -> str:
    """Fetch a parameter from AWS Systems Manager Parameter Store.

    Args:
        parameter_name: Name of the parameter (e.g., '/agentcore/dev/identity/pool_id')
        with_decryption: Whether to decrypt SecureString parameters

    Returns:
        Parameter value as string

    Raises:
        RuntimeError: If parameter not found or AWS credentials invalid
    """
    try:
        ssm = boto3.client("ssm")
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=with_decryption)
        return response["Parameter"]["Value"]
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ParameterNotFound":
            raise RuntimeError(
                f"Configuration parameter '{parameter_name}' not found. "
                "Ensure infrastructure is deployed."
            ) from e
        raise RuntimeError(f"Failed to retrieve parameter '{parameter_name}': {e}") from e


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    """Load application configuration from SSM Parameter Store.

    Configuration is cached after first load for performance.

    Returns:
        AppConfig with Cognito and Gateway settings

    Raises:
        RuntimeError: If required parameters are missing
    """
    environment = os.getenv("AGENTCORE_ENV", "dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    # Build parameter paths
    base_path = f"/agentcore/{environment}"

    try:
        # Fetch Cognito configuration
        pool_id = get_ssm_parameter(f"{base_path}/identity/pool_id")
        client_id = get_ssm_parameter(f"{base_path}/identity/frontend_client_id")
        client_secret = get_ssm_parameter(
            f"{base_path}/identity/frontend_client_secret", with_decryption=True
        )
        domain = get_ssm_parameter(f"{base_path}/identity/domain")

        # Fetch API Gateway configuration
        invoke_url = get_ssm_parameter(f"{base_path}/gateway/invoke_url")

        # Fetch Frontend Gateway configuration
        frontend_gateway_url = get_ssm_parameter(f"{base_path}/frontend-gateway/api_endpoint")

        return AppConfig(
            cognito=CognitoConfig(
                pool_id=pool_id,
                client_id=client_id,
                client_secret=client_secret,
                domain=domain,
                region=region,
            ),
            gateway=GatewayConfig(invoke_url=invoke_url),
            frontend_gateway_url=frontend_gateway_url,
            environment=environment,
        )
    except RuntimeError as e:
        raise RuntimeError(
            f"Failed to load configuration for environment '{environment}'. "
            "Verify infrastructure is deployed and SSM parameters exist."
        ) from e
