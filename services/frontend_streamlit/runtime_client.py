"""AgentCore Runtime client for invoking deployed agents via Frontend Gateway."""

from __future__ import annotations

import logging
from typing import Any

import requests
import streamlit as st

from services.frontend_streamlit.config import load_config

logger = logging.getLogger(__name__)


class AgentCoreRuntimeClient:
    """Client for invoking AgentCore Runtime via Frontend Gateway."""

    def __init__(
        self,
        runtime_name: str = "customersupport",
        runtime_arn: str | None = None,  # noqa: ARG002 - Deprecated, ignored
        region: str = "us-east-1",
    ):
        """Initialize the runtime client.

        Args:
            runtime_name: Name of the AgentCore runtime
            runtime_arn: Ignored (Gateway handles resolution)
            region: AWS region
        """
        self.runtime_name = runtime_name
        self.region = region
        logger.info(f"Initialized runtime client for agent: {runtime_name}")

    def invoke_agent(
        self,
        message: str,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Invoke the AgentCore Runtime via Gateway.

        Args:
            message: User's query
            user_id: User identifier
            session_id: Conversation session ID

        Returns:
            Agent response dictionary with 'output' field

        Raises:
            RuntimeError: If invocation fails
        """

        # Get token from session state
        # Use ID token to ensure custom attributes (like allowed_agents) are available
        from services.frontend_streamlit.session import get_session_state

        state = get_session_state()
        token = state.id_token
        if not token:
            raise RuntimeError("No ID token found. Please log in.")

        try:
            config = load_config()
            base_url = config.frontend_gateway_url.rstrip("/")
            url = f"{base_url}/agents/{self.runtime_name}/invoke"

            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

            payload = {"message": message, "sessionId": session_id, "userId": user_id}

            logger.info(f"Invoking agent {self.runtime_name} via Gateway")

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 401:
                raise RuntimeError("Unauthorized. Please log in again.")
            if response.status_code == 403:
                raise RuntimeError(f"Access denied to agent {self.runtime_name}")
            if response.status_code == 404:
                raise RuntimeError(f"Agent {self.runtime_name} not found")

            response.raise_for_status()

            data = response.json()
            return {
                "output": data.get("output", ""),
                "session_id": data.get("sessionId", session_id),
                "user_id": data.get("userId", user_id),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Gateway invocation failed: {e}")
            raise RuntimeError(f"Failed to invoke agent: {e}") from e


def get_runtime_client(
    runtime_name: str | None = None,
    runtime_arn: str | None = None,  # noqa: ARG001 - Deprecated, kept for compatibility
) -> AgentCoreRuntimeClient:
    """Factory function to create an AgentCoreRuntimeClient.

    Args:
        runtime_name: Name of the AgentCore runtime (if None, reads from session state)
        runtime_arn: Ignored

    Returns:
        Configured AgentCoreRuntimeClient instance
    """
    # Read selected agent from session state if not provided
    if runtime_name is None:
        runtime_name = st.session_state.get("selected_agent", "customer-support")
        logger.info(f"Using selected agent from session state: {runtime_name}")

    return AgentCoreRuntimeClient(runtime_name=runtime_name)
