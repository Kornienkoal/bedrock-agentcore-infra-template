"""Unit tests for OAuth state encoding and decoding."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.frontend_streamlit.oauth_state import (
    STATE_MAX_AGE_SECONDS,
    OAuthStateError,
    decode_oauth_state,
    encode_oauth_state,
)


@pytest.fixture
def mock_config():
    """Provide a mocked configuration with a deterministic client secret."""
    with patch("services.frontend_streamlit.oauth_state.load_config") as mock:
        config = MagicMock()
        config.cognito.client_secret = "test-client-secret"
        mock.return_value = config
        yield mock


class TestOAuthState:
    """Tests for signed OAuth state helpers.

    Note: mock_config fixture is required to mock SSM parameter loading
    during module import, even though not directly used in tests.
    """

    def test_encode_decode_roundtrip(self, mock_config):  # noqa: ARG002
        state_value = encode_oauth_state("verifier-123")
        payload = decode_oauth_state(state_value)

        assert payload["verifier"] == "verifier-123"
        assert payload["v"] == 1
        assert "nonce" in payload and isinstance(payload["nonce"], str)
        assert isinstance(payload["iat"], int)

    def test_decode_rejects_tampered_value(self, mock_config):  # noqa: ARG002
        state_value = encode_oauth_state("verifier-123")
        tampered = state_value[:-1] + ("A" if state_value[-1] != "A" else "B")

        with pytest.raises(OAuthStateError):
            decode_oauth_state(tampered)

    def test_decode_rejects_expired_payload(self, mock_config, monkeypatch):  # noqa: ARG002
        # Freeze time for encoding
        initial_time = 1_700_000_000
        monkeypatch.setattr(
            "services.frontend_streamlit.oauth_state.time.time", lambda: initial_time
        )
        state_value = encode_oauth_state("verifier-abc")

        # Advance time beyond the allowed age
        monkeypatch.setattr(
            "services.frontend_streamlit.oauth_state.time.time",
            lambda: initial_time + STATE_MAX_AGE_SECONDS + 10,
        )

        with pytest.raises(OAuthStateError, match="expired"):
            decode_oauth_state(state_value)

    def test_decode_rejects_missing_state(self, mock_config):  # noqa: ARG002
        with pytest.raises(OAuthStateError, match="missing"):
            decode_oauth_state("")
