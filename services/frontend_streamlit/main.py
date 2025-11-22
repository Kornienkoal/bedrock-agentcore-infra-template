"""Streamlit app entrypoint for AgentCore customer support demo."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add parent directories to path for absolute imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import requests  # noqa: E402
import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from services.frontend_streamlit.auth import (  # noqa: E402
    build_authorization_url,
    build_logout_url,
    decode_id_token,
    exchange_code_for_tokens,
    generate_pkce_pair,
    refresh_access_token,
)
from services.frontend_streamlit.components import (  # noqa: E402
    render_auth_status,
    render_chat_interface,
    render_error,
    render_header,
    render_login_button,
)
from services.frontend_streamlit.config import load_config  # noqa: E402
from services.frontend_streamlit.oauth_state import (  # noqa: E402
    OAuthStateError,
    decode_oauth_state,
    encode_oauth_state,
)
from services.frontend_streamlit.runtime_client import get_runtime_client  # noqa: E402
from services.frontend_streamlit.runtime_client_local import get_local_runtime_client  # noqa: E402
from services.frontend_streamlit.session import (  # noqa: E402
    add_message,
    ensure_agent_session,
    get_session_id,
    get_session_state,
    init_session_state,
    is_token_expired,
    reset_session_state,
    set_tokens,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

for noisy_logger in (
    "botocore",
    "boto3",
    "urllib3.connectionpool",
):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Check if running in local mode (no auth)
LOCAL_MODE = os.environ.get("AGENTCORE_LOCAL_MODE", "false").lower() == "true"
LOCAL_RUNTIME_URL = os.environ.get("AGENTCORE_LOCAL_RUNTIME_URL", "http://localhost:8000")

# App configuration
REDIRECT_URI = "http://localhost:8501"

# Available agents (Phase 2: hardcoded list; will be dynamic in future phases)
AVAILABLE_AGENTS = [
    {
        "id": "customer-support",
        "name": "Customer Support",
        "description": "Product inquiries and troubleshooting",
    },
    {
        "id": "warranty-docs",
        "name": "Warranty & Docs",
        "description": "Warranty checking and documentation",
    },
]


@st.cache_data(ttl=300)
def fetch_agents(access_token: str) -> list[dict]:
    """Fetch available agents from the Frontend Gateway."""
    if LOCAL_MODE:
        return AVAILABLE_AGENTS

    try:
        config = load_config()
        # Ensure URL doesn't end with slash to avoid double slash
        base_url = config.frontend_gateway_url.rstrip("/")
        url = f"{base_url}/agents"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        return data.get("agents", [])
    except Exception as e:
        logger.error(f"Failed to fetch agents: {e}")
        return []


def render_agent_selector() -> None:
    """Render agent selection dropdown and maintain per-agent state."""

    state = get_session_state()

    # In local mode, we might not have a token, but we have AVAILABLE_AGENTS
    if LOCAL_MODE:
        agents = AVAILABLE_AGENTS
    elif state.authenticated and state.id_token:
        agents = fetch_agents(state.id_token)
    else:
        # Not authenticated yet, cannot fetch agents
        return

    if not agents:
        if state.authenticated:
            st.sidebar.warning("No agents available.")
        return

    # Initialize selected agent in session state if not set
    if "selected_agent" not in st.session_state:
        st.session_state.selected_agent = agents[0]["id"]

    # Ensure selected agent is valid (in case list changed)
    agent_ids = [a["id"] for a in agents]
    if st.session_state.selected_agent not in agent_ids:
        st.session_state.selected_agent = agents[0]["id"]

    ensure_agent_session(st.session_state.selected_agent)

    # Render selector in sidebar
    with st.sidebar:
        st.markdown("### Agent Selection")

        agent_options = {
            agent["id"]: f"{agent['name']} - {agent.get('description', '')}" for agent in agents
        }

        selected = st.selectbox(
            "Choose an agent:",
            options=list(agent_options.keys()),
            format_func=lambda x: agent_options[x],
            index=list(agent_options.keys()).index(st.session_state.selected_agent),
            key="agent_selector",
        )

        # Update session state if changed
        if selected != st.session_state.selected_agent:
            st.session_state.selected_agent = selected
            ensure_agent_session(selected)
            st.rerun()


def render_app() -> None:
    """Main application entrypoint."""
    st.set_page_config(
        page_title="AgentCore Customer Support",
        page_icon="🤖",
        layout="wide",
    )

    # Initialize session state
    init_session_state()

    # Local mode - bypass authentication
    if LOCAL_MODE:
        state = get_session_state()
        state.authenticated = True
        state.user_id = "local-user"
        state.email = "local@dev"
        logger.info(f"🏠 Running in LOCAL MODE - connecting to {LOCAL_RUNTIME_URL}")

    # Handle OAuth callback (skip in local mode)
    if not LOCAL_MODE:
        handle_oauth_callback()

    # Handle logout
    if st.session_state.get("should_logout"):
        handle_logout()
        return

    # Handle login redirect
    if st.session_state.get("should_login"):
        handle_login_redirect()
        return

    # Render header
    render_header()
    render_auth_status()

    # Agent selector (Phase 2: UI skeleton only, no behavior change)
    render_agent_selector()

    state = get_session_state()

    if not state.authenticated:
        # Generate login URL if needed
        login_url = None
        if not st.session_state.get("should_login"):
            # Pre-generate login URL so we can show it as a direct link
            code_verifier, code_challenge = generate_pkce_pair()
            try:
                state_value = encode_oauth_state(code_verifier)
                login_url = build_authorization_url(
                    state=state_value,
                    code_challenge=code_challenge,
                    redirect_uri=REDIRECT_URI,
                )
            except OAuthStateError:
                pass  # Fall back to button-based flow

        # Show login screen with direct link
        render_login_button(login_url=login_url)
    else:
        # Refresh token if needed
        if is_token_expired() and state.refresh_token:
            try:
                logger.info("Refreshing access token")
                tokens = refresh_access_token(state.refresh_token)
                set_tokens(
                    access_token=tokens.access_token,
                    id_token=tokens.id_token,
                    refresh_token=tokens.refresh_token or state.refresh_token,
                    expires_in=tokens.expires_in,
                )
            except ValueError as e:
                logger.error(f"Token refresh failed: {e}")
                render_error("Session expired. Please log in again.")
                if st.button("Re-authenticate"):
                    reset_session_state()
                    st.rerun()
                return

        # Handle pending message
        if pending := st.session_state.get("pending_message"):
            handle_message_send(pending)
            del st.session_state.pending_message
            st.rerun()

        # Render chat interface
        render_chat_interface()


def handle_oauth_callback() -> None:
    """Handle OAuth2 callback with authorization code."""
    # Check query parameters
    params = st.query_params

    if "code" in params:
        code = params["code"]
        returned_state = params.get("state")

        session_state = get_session_state()

        # SECURITY: Prevent code reuse - check if already authenticated
        if session_state.authenticated:
            st.query_params.clear()
            st.rerun()
            return

        if not returned_state:
            logger.warning("OAuth callback missing state parameter")
            st.query_params.clear()
            render_error("Invalid authentication request. Please try again.")
            st.stop()
            return

        try:
            state_payload = decode_oauth_state(returned_state)
            code_verifier = state_payload["verifier"]
        except OAuthStateError as exc:
            logger.warning(f"Invalid OAuth state payload: {exc}")
            st.query_params.clear()
            render_error("Invalid authentication request. Please try again.")
            st.stop()
            return

        # Exchange code for tokens
        try:
            logger.info("Exchanging authorization code for tokens")
            tokens = exchange_code_for_tokens(
                authorization_code=code,
                code_verifier=code_verifier,
                redirect_uri=REDIRECT_URI,
            )

            # Store tokens in session
            set_tokens(
                access_token=tokens.access_token,
                id_token=tokens.id_token,
                refresh_token=tokens.refresh_token,
                expires_in=tokens.expires_in,
            )

            # Extract user info from ID token
            claims = decode_id_token(tokens.id_token)
            session_state.user_id = claims.get("sub")
            session_state.email = claims.get("email")
            session_state.username = claims.get("cognito:username")

            # SECURITY: Clear query parameters immediately to prevent code reuse
            st.query_params.clear()
            logger.info(f"User {session_state.email} authenticated successfully")

            # Force page reload to clear URL from browser history
            st.rerun()

        except ValueError as e:
            logger.error(f"Authentication failed: {e}")
            # SECURITY: Clear query params on error to prevent retry
            st.query_params.clear()
            render_error(f"Authentication failed: {e}")
            st.stop()

    elif "error" in params:
        # User cancelled or error occurred
        error = params.get("error")
        error_description = params.get("error_description", "Unknown error")
        logger.warning(f"OAuth error: {error} - {error_description}")
        # SECURITY: Clear params immediately
        st.query_params.clear()
        render_error(f"Authentication failed: {error_description}")
        st.stop()


def handle_login_redirect() -> None:
    """Initiate OAuth2 login flow with PKCE."""
    # Generate PKCE pair
    code_verifier, code_challenge = generate_pkce_pair()

    try:
        state_value = encode_oauth_state(code_verifier)
    except OAuthStateError as exc:
        logger.error(f"Failed to encode OAuth state: {exc}")
        render_error("Unable to initiate authentication. Please try again.")
        return

    # Reset login flag so we do not loop if redirect is delayed
    st.session_state.should_login = False

    # Build authorization URL
    auth_url = build_authorization_url(
        state=state_value,
        code_challenge=code_challenge,
        redirect_uri=REDIRECT_URI,
    )

    logger.info(f"Generated Cognito login URL: {auth_url}")

    # Show login link (automatic redirects don't work reliably in Streamlit)
    st.markdown("### Redirecting to Cognito...")
    st.markdown(
        f'<a href="{auth_url}" target="_self">Click here if not redirected automatically</a>',
        unsafe_allow_html=True,
    )

    # Use JavaScript to trigger immediate redirect
    st.markdown(
        f"""
    <script>
        window.location.replace("{auth_url}");
    </script>
    """,
        unsafe_allow_html=True,
    )
    st.stop()


def handle_logout() -> None:
    """Handle user logout."""
    logger.info("User logging out")

    # Build logout URL
    logout_url = build_logout_url(redirect_uri=REDIRECT_URI)

    # Reset session
    reset_session_state()

    # Redirect to Cognito logout using HTML component
    redirect_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script>
            window.parent.location.href = "{logout_url}";
        </script>
    </head>
    <body>
        <p>Logging out...</p>
    </body>
    </html>
    """
    components.html(redirect_html, height=0)
    st.stop()


def handle_message_send(payload: dict[str, str]) -> None:
    """Handle sending a message to the active agent.

    Args:
        payload: Dict containing ``agent_id`` and ``prompt`` keys
    """

    agent_id = payload.get("agent_id") or st.session_state.get("selected_agent")
    message = payload.get("prompt", "")

    if not agent_id or not message:
        logger.warning("No agent or message provided for invocation; skipping")
        return

    ensure_agent_session(agent_id)
    state = get_session_state()

    # Add user message to history
    add_message(agent_id, "user", message)

    # Get agent response
    try:
        # Use local or remote runtime client based on mode
        if LOCAL_MODE:
            client = get_local_runtime_client(
                runtime_name=agent_id,
                base_url=LOCAL_RUNTIME_URL,
            )
        else:
            client = get_runtime_client(runtime_name=agent_id)

        response = client.invoke_agent(
            message=message,
            user_id=state.user_id,
            session_id=get_session_id(agent_id),
        )

        agent_message = response.get("output", "No response from agent")
        add_message(agent_id, "assistant", agent_message)

    except RuntimeError as e:
        error_msg = str(e)
        logger.error(f"Agent invocation failed: {error_msg}")
        error_message = f"❌ {error_msg}"
        add_message(agent_id, "assistant", error_message)

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Agent invocation failed: {error_msg}")
        error_message = f"❌ {error_msg}"
        add_message(agent_id, "assistant", error_message)


if __name__ == "__main__":
    render_app()
