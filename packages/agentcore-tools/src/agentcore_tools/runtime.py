"""Runtime utilities for AgentCore agents using Strands framework.

Provides a standardized invoke handler that encapsulates common patterns:
- Config loading and observability setup
- Gateway tool loading with authorization
- Memory hooks integration
- Model and agent creation
- Error handling
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from agentcore_common import (
    get_gateway_url,
    load_agent_config,
    resolve_authorization_header,
    setup_observability,
)
from agentcore_common.gateway import filter_tools_by_allowed
from bedrock_agentcore.memory import MemoryClient as AcMemoryClient
from strands import Agent
from strands.hooks.registry import HookProvider
from strands.models import BedrockModel

from .gateway import create_mcp_client
from .memory import MemoryHooks


class AgentRuntime:
    """Manages agent runtime lifecycle with lazy config loading."""

    def __init__(self, agent_name: str):
        """Initialize runtime for a specific agent.

        Args:
            agent_name: Agent name used to load config (e.g., 'customer-support')
        """
        self.agent_name = agent_name
        self._config: Any | None = None
        self._logger: logging.Logger | None = None

    @property
    def config(self):
        """Lazy load configuration on first access."""
        if self._config is None:
            self._config = load_agent_config(agent_name=self.agent_name)
            self._logger = setup_observability(
                agent_name=self._config.name,
                log_level=self._config.observability.get("log_level", "INFO"),
                enable_xray=self._config.observability.get("xray_tracing", True),
            )
        return self._config

    @property
    def logger(self) -> logging.Logger:
        """Get logger (triggers config load if needed)."""
        _ = self.config  # Ensure config is loaded
        assert self._logger is not None
        return self._logger

    def create_invoke_handler(
        self,
        local_tools: list[Callable] | Callable[[], list[Callable]],
    ) -> Callable:
        """Create a standardized invoke handler for the agent.

        Args:
            local_tools: List of tool functions, or a callable that returns tools

        Returns:
            Async invoke handler compatible with BedrockAgentCoreApp.entrypoint

        Example:
            >>> from tools.product_tools import get_product_info, search_documentation
            >>>
            >>> runtime = AgentRuntime("customer-support")
            >>> invoke = runtime.create_invoke_handler([get_product_info, search_documentation])
            >>>
            >>> # Or with dynamic tool loading:
            >>> def get_tools():
            ...     from tools.product_tools import get_product_info
            ...     return [get_product_info]
            >>> invoke = runtime.create_invoke_handler(get_tools)
        """

        async def invoke(payload: dict, context: Any = None) -> str:
            """AgentCore Runtime entrypoint function.

            Args:
                payload: Request payload with 'prompt' field
                context: Runtime context with request_headers for Authorization

            Returns:
                Agent response text
            """
            config = self.config
            logger = self.logger

            # Extract user input
            user_input = payload.get("prompt", "")
            logger.info(f"Agent invocation started: {user_input[:100]}...")

            # Get region from config
            region = config.runtime.region

            # Get Gateway configuration (safely handle dict or object)
            gateway_config = getattr(config, "gateway", {})
            gateway_id = (
                gateway_config.get("gateway_id")
                if isinstance(gateway_config, dict)
                else getattr(gateway_config, "gateway_id", None)
            )

            gateway_url = None
            if gateway_id:
                try:
                    gateway_url = get_gateway_url(gateway_id, region=region)
                    logger.info(f"Using Gateway: {gateway_url} (ID: {gateway_id})")
                except Exception as e:
                    logger.warning(f"Failed to get Gateway URL: {e}")

            # Resolve local tools
            tools_list = local_tools() if callable(local_tools) else local_tools
            all_tools = list(tools_list)

            # Resolve Authorization header (caller token or M2M fallback)
            # Handle None context case (local testing)
            header_value = None
            if gateway_url:
                try:
                    header_value = resolve_authorization_header(
                        context, getattr(config, "identity", {}), logger
                    )
                except Exception as e:
                    logger.warning(f"Failed to resolve authorization: {e}")

            # Load Gateway tools and invoke agent within MCP client context
            if gateway_url and header_value:
                try:
                    with create_mcp_client(gateway_url, header_value) as client:
                        gateway_tools = client.list_tools_sync()
                        filtered = filter_tools_by_allowed(gateway_tools, config.gateway, logger)
                        all_tools.extend(filtered)

                        # Build and invoke agent (MCP client stays open during execution)
                        response_text = self._build_and_invoke(
                            user_input=user_input,
                            tools=all_tools,
                            payload=payload,
                            config=config,
                            logger=logger,
                        )
                except Exception as exc:  # pragma: no cover - fallback logging path
                    logger.error("Agent error with Gateway tools", exc_info=True)
                    return f"Error: {exc}"
            else:
                if gateway_url:
                    logger.info("No Authorization available for Gateway; using local tools only")

                try:
                    # Invoke with local tools only
                    response_text = self._build_and_invoke(
                        user_input=user_input,
                        tools=all_tools,
                        payload=payload,
                        config=config,
                        logger=logger,
                    )
                except Exception as exc:  # pragma: no cover - fallback logging path
                    logger.error("Agent error", exc_info=True)
                    return f"Error: {exc}"

            logger.info("Agent invocation completed successfully")
            return response_text

        return invoke

    def _build_and_invoke(
        self,
        user_input: str,
        tools: list,
        payload: dict,
        config: Any,
        logger: logging.Logger,
    ) -> str:
        """Build agent and invoke with user input.

        Args:
            user_input: User's prompt
            tools: Complete list of tools (local + gateway)
            payload: Original request payload
            config: Agent configuration
            logger: Logger instance

        Returns:
            Agent response text
        """
        # Create Bedrock model from config
        model = BedrockModel(
            model_id=config.model.model_id,
            temperature=config.model.temperature,
            max_tokens=config.model.max_tokens,
        )

        hooks: list[HookProvider] = []

        # Setup memory hooks if enabled
        memory_cfg = getattr(config, "memory", None)
        if (
            memory_cfg
            and getattr(memory_cfg, "enabled", False)
            and getattr(memory_cfg, "memory_id", None)
        ):
            try:
                # Derive actor_id and session_id (allow payload overrides)
                actor_id = payload.get("actor_id") or payload.get("user_id") or "anonymous"
                session_id = (
                    payload.get("session_id") or payload.get("conversation_id") or "session-unknown"
                )

                # Initialize Bedrock AgentCore Memory client
                ac_memory_client = AcMemoryClient(region_name=config.runtime.region)
                hooks.append(
                    MemoryHooks(
                        memory_client=ac_memory_client,
                        memory_id=memory_cfg.memory_id,
                        actor_id=actor_id,
                        session_id=session_id,
                        logger=logger,
                    )
                )
                logger.info(
                    f"AgentCore Memory enabled: memory_id={memory_cfg.memory_id}, "
                    f"actor_id={actor_id}, session_id={session_id}"
                )
            except Exception as e:  # pragma: no cover - non-fatal path
                logger.warning(f"Failed to initialize AgentCore Memory hooks: {e}")

        # Create Strands agent with config-based settings and optional hooks
        agent_kwargs = {
            "model": model,
            "tools": tools,
            "system_prompt": config.system_prompt,
        }

        # Add hooks if supported by Agent version
        sig = inspect.signature(Agent)
        if "hooks" in sig.parameters:
            agent_kwargs["hooks"] = hooks

        agent = Agent(**agent_kwargs)

        # Invoke agent
        logger.info(f"Invoking agent with {len(tools)} total tools...")
        response = agent(user_input)

        # Extract response text safely
        try:
            result: str = response.message["content"][0]["text"]
            return result
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Unexpected response structure: {response}")
            raise RuntimeError(f"Failed to extract response text: {e}") from e


def create_runtime_app(
    agent_name: str,
    local_tools: list[Callable] | Callable[[], list[Callable]],
) -> tuple[Any, Callable]:
    """Create a BedrockAgentCoreApp with standardized invoke handler.

    This is a convenience function that combines app creation and runtime setup.

    Args:
        agent_name: Agent name for config loading
        local_tools: List of tool functions or callable returning tools

    Returns:
        Tuple of (app, invoke_handler)

    Example:
        >>> from bedrock_agentcore.runtime import BedrockAgentCoreApp
        >>> from tools.product_tools import get_product_info, search_documentation
        >>>
        >>> app, invoke = create_runtime_app(
        ...     agent_name="customer-support",
        ...     local_tools=[get_product_info, search_documentation]
        ... )
        >>>
        >>> app.entrypoint(invoke)
        >>>
        >>> if __name__ == "__main__":
        ...     app.run()
    """
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    app = BedrockAgentCoreApp()
    runtime = AgentRuntime(agent_name)
    invoke = runtime.create_invoke_handler(local_tools)

    return app, invoke
