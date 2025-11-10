"""Unit tests for correlation ID helpers."""

import pytest
from agentcore_governance.correlation import CorrelationContext, new_correlation_context


class TestCorrelationContext:
    """Tests for CorrelationContext."""

    def test_create_context_with_all_fields(self):
        """Test creating a correlation context with all fields."""
        ctx = CorrelationContext(
            trace_id="abc123",
            user="user@example.com",
            agent="customer-support",
            tool="web_search",
        )

        assert ctx.trace_id == "abc123"
        assert ctx.user == "user@example.com"
        assert ctx.agent == "customer-support"
        assert ctx.tool == "web_search"

    def test_to_headers_full(self):
        """Test converting context to headers with all fields."""
        ctx = CorrelationContext(
            trace_id="abc123",
            user="user@example.com",
            agent="customer-support",
            tool="web_search",
        )

        headers = ctx.to_headers()

        assert "X-Correlation-Id" in headers
        correlation_id = headers["X-Correlation-Id"]
        assert "trace=abc123" in correlation_id
        assert "user=user@example.com" in correlation_id
        assert "agent=customer-support" in correlation_id
        assert "tool=web_search" in correlation_id

    def test_to_headers_minimal(self):
        """Test converting context with only trace_id."""
        ctx = CorrelationContext(trace_id="xyz789")

        headers = ctx.to_headers()

        assert headers["X-Correlation-Id"] == "trace=xyz789"

    def test_context_immutable(self):
        """Test that CorrelationContext is immutable."""
        ctx = CorrelationContext(trace_id="abc123")

        with pytest.raises(AttributeError):
            ctx.trace_id = "modified"  # type: ignore


class TestNewCorrelationContext:
    """Tests for new_correlation_context."""

    def test_creates_unique_trace_ids(self):
        """Test that each new context gets a unique trace_id."""
        ctx1 = new_correlation_context()
        ctx2 = new_correlation_context()

        assert ctx1.trace_id != ctx2.trace_id

    def test_creates_with_optional_fields(self):
        """Test creating context with optional metadata."""
        ctx = new_correlation_context(
            user="user@example.com",
            agent="customer-support",
            tool="check_warranty",
        )

        assert ctx.trace_id  # Should have a generated trace_id
        assert len(ctx.trace_id) == 32  # UUID hex format
        assert ctx.user == "user@example.com"
        assert ctx.agent == "customer-support"
        assert ctx.tool == "check_warranty"

    def test_creates_with_partial_fields(self):
        """Test creating context with only some optional fields."""
        ctx = new_correlation_context(agent="warranty-docs")

        assert ctx.trace_id
        assert ctx.user is None
        assert ctx.agent == "warranty-docs"
        assert ctx.tool is None
