"""Unit tests for agentcore_tools.runtime module."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class FakeAgent:
    """Minimal fake Strands Agent for testing."""

    def __init__(self, model=None, tools=None, system_prompt=None, hooks=None):
        self.model = model
        self.tools = tools or []
        self.system_prompt = system_prompt
        self.hooks = hooks or []

    def __call__(self, user_input):
        return SimpleNamespace(message={"content": [{"text": f"Response to: {user_input}"}]})


@pytest.fixture
def mock_config():
    """Create a mock agent configuration."""
    cfg = MagicMock()
    cfg.name = "test-agent"
    cfg.model.model_id = "test-model"
    cfg.model.temperature = 0.7
    cfg.model.max_tokens = 1000
    cfg.system_prompt = "You are a test agent"
    cfg.runtime.region = "us-east-1"
    cfg.gateway = {"gateway_id": "test-gw-123"}
    cfg.identity = {}
    cfg.observability = {"log_level": "INFO", "xray_tracing": False}
    return cfg


class TestAgentRuntime:
    """Test AgentRuntime class."""

    def test_lazy_config_loading(self, mock_config):
        """Config should be loaded lazily on first access."""
        from agentcore_tools.runtime import AgentRuntime

        with (
            patch("agentcore_tools.runtime.load_agent_config", return_value=mock_config),
            patch("agentcore_tools.runtime.setup_observability", return_value=MagicMock()),
        ):
            runtime = AgentRuntime("test-agent")

            # Config not loaded yet
            assert runtime._config is None

            # Access config triggers loading
            config = runtime.config
            assert config == mock_config
            assert runtime._config is not None

    def test_create_invoke_handler_with_list(self, mock_config):
        """Should create invoke handler with list of tools."""
        from agentcore_tools.runtime import AgentRuntime

        def test_tool():
            """Test tool."""
            return "result"

        with (
            patch("agentcore_tools.runtime.load_agent_config", return_value=mock_config),
            patch("agentcore_tools.runtime.setup_observability", return_value=MagicMock()),
            patch("agentcore_tools.runtime.get_gateway_url", return_value=None),
            patch("agentcore_tools.runtime.BedrockModel"),
            patch("agentcore_tools.runtime.Agent", FakeAgent),
        ):
            runtime = AgentRuntime("test-agent")
            invoke = runtime.create_invoke_handler([test_tool])

            assert callable(invoke)

    def test_create_invoke_handler_with_callable(self, mock_config):
        """Should create invoke handler with callable that returns tools."""
        from agentcore_tools.runtime import AgentRuntime

        def test_tool():
            """Test tool."""
            return "result"

        def get_tools():
            return [test_tool]

        with (
            patch("agentcore_tools.runtime.load_agent_config", return_value=mock_config),
            patch("agentcore_tools.runtime.setup_observability", return_value=MagicMock()),
            patch("agentcore_tools.runtime.get_gateway_url", return_value=None),
            patch("agentcore_tools.runtime.BedrockModel"),
            patch("agentcore_tools.runtime.Agent", FakeAgent),
        ):
            runtime = AgentRuntime("test-agent")
            invoke = runtime.create_invoke_handler(get_tools)

            assert callable(invoke)

    @pytest.mark.asyncio
    @pytest.mark.skip_precommit
    async def test_invoke_handler_basic_flow(self, mock_config):
        """Invoke handler should process basic requests."""
        from agentcore_tools.runtime import AgentRuntime

        def test_tool():
            """Test tool."""
            return "result"

        with (
            patch("agentcore_tools.runtime.load_agent_config", return_value=mock_config),
            patch("agentcore_tools.runtime.setup_observability", return_value=MagicMock()),
            patch("agentcore_tools.runtime.get_gateway_url", return_value=None),
            patch("agentcore_tools.runtime.BedrockModel"),
            patch("agentcore_tools.runtime.Agent", FakeAgent),
        ):
            runtime = AgentRuntime("test-agent")
            invoke = runtime.create_invoke_handler([test_tool])

            result = await invoke({"prompt": "test question"}, context=MagicMock())
            assert "test question" in result

    @pytest.mark.asyncio
    @pytest.mark.skip_precommit
    async def test_invoke_handler_with_gateway(self, mock_config):
        """Invoke handler should load gateway tools when available."""
        from agentcore_tools.runtime import AgentRuntime

        def test_tool():
            """Test tool."""
            return "result"

        mock_mcp_client = MagicMock()
        mock_mcp_client.__enter__ = MagicMock(return_value=mock_mcp_client)
        mock_mcp_client.__exit__ = MagicMock(return_value=False)
        mock_mcp_client.list_tools_sync = MagicMock(return_value=[])

        with (
            patch("agentcore_tools.runtime.load_agent_config", return_value=mock_config),
            patch("agentcore_tools.runtime.setup_observability", return_value=MagicMock()),
            patch(
                "agentcore_tools.runtime.get_gateway_url",
                return_value="https://gateway.example.com",
            ),
            patch(
                "agentcore_tools.runtime.resolve_authorization_header", return_value="Bearer token"
            ),
            patch("agentcore_tools.runtime.create_mcp_client", return_value=mock_mcp_client),
            patch("agentcore_tools.runtime.filter_tools_by_allowed", return_value=[]),
            patch("agentcore_tools.runtime.BedrockModel"),
            patch("agentcore_tools.runtime.Agent", FakeAgent),
        ):
            runtime = AgentRuntime("test-agent")
            invoke = runtime.create_invoke_handler([test_tool])

            await invoke({"prompt": "test"}, context=MagicMock())
            # MCP client should have been called
            mock_mcp_client.list_tools_sync.assert_called_once()


class TestCreateRuntimeApp:
    """Test create_runtime_app convenience function."""

    def test_returns_app_and_invoke(self, mock_config):
        """Should return BedrockAgentCoreApp and invoke handler."""
        from agentcore_tools.runtime import create_runtime_app

        def test_tool():
            """Test tool."""
            return "result"

        with (
            patch("agentcore_tools.runtime.load_agent_config", return_value=mock_config),
            patch("agentcore_tools.runtime.setup_observability", return_value=MagicMock()),
        ):
            app, invoke = create_runtime_app("test-agent", [test_tool])

            # Should return app instance
            assert app is not None
            assert hasattr(app, "entrypoint")

            # Should return callable invoke handler
            assert callable(invoke)
