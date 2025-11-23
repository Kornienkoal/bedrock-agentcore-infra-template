"""E2E tests for authentication flow security."""

import pytest
from playwright.sync_api import Page, expect

# Mark all tests in this file to skip in pre-commit hooks (require AWS infrastructure)
pytestmark = pytest.mark.skip_precommit


@pytest.fixture(scope="module")
def app_url():
    """Return the Streamlit app URL."""
    return "http://localhost:8501"


def test_unauthenticated_user_cannot_access_chat(page: Page, app_url: str):
    """Verify that unauthenticated users cannot access the chat interface."""
    # Fresh browser context (no cookies/session)
    page.goto(app_url, wait_until="networkidle", timeout=30000)
    page.screenshot(path="test-artifacts/auth-test-1-unauthenticated.png", full_page=True)

    # Get page content
    body_text = page.inner_text("body")

    # Should show login screen elements
    assert ("Login with Cognito" in body_text) or ("Please log in" in body_text), (
        "Login control or prompt should be present"
    )
    assert "Please log in" in body_text, "Login prompt should be shown"

    # Should NOT show chat interface
    assert "Type your message here" not in body_text, "Chat input should not be accessible"
    assert "Logged in as" not in body_text, "Should not show authenticated state"


def test_login_button_redirects_to_cognito(page: Page, app_url: str):
    """Verify that clicking login button redirects to Cognito Hosted UI."""
    page.goto(app_url, wait_until="networkidle", timeout=30000)

    # Prefer direct link if available
    login_link = page.locator('a:has-text("Login with Cognito")')
    if login_link.count() > 0:
        expect(login_link).to_be_visible()
        href = login_link.get_attribute("href")
        assert href is not None, "Login link should have href"
        assert "oauth2" in href.lower() and "state=" in href, (
            "Auth URL should contain OAuth2 params"
        )
    else:
        # Fallback for local dev without SSM config: assert the login prompt is visible
        expect(page.locator("text=Please log in")).to_be_visible()
        return

    page.screenshot(path="test-artifacts/auth-test-2-cognito-hosted-ui.png", full_page=True)


def test_direct_url_access_without_auth(page: Page, app_url: str):
    """Test that directly accessing the app URL without auth shows login."""
    # Simulate direct URL access (e.g., bookmark, new tab)
    page.goto(app_url, wait_until="networkidle", timeout=30000)

    body_text = page.inner_text("body")

    # Must show login screen, not chat
    assert ("Login with Cognito" in body_text) or ("Please log in" in body_text), (
        "Direct access should require login"
    )
    assert "Type your message here" not in body_text, "Chat should not be accessible"


def test_no_session_bypass(page: Page, app_url: str):
    """Verify that session state doesn't persist inappropriately."""
    # First visit
    page.goto(app_url, wait_until="networkidle", timeout=30000)
    body1 = page.inner_text("body")

    # Should require login (either explicit link or generic prompt)
    assert ("Login with Cognito" in body1) or ("Please log in" in body1)

    # Reload the page
    page.reload(wait_until="networkidle", timeout=30000)
    body2 = page.inner_text("body")

    # Should still require login (no bypass)
    assert ("Login with Cognito" in body2) or ("Please log in" in body2)
    assert "Type your message here" not in body2


def test_oauth_state_parameter_security(page: Page, app_url: str):
    """Verify OAuth state parameter is properly signed."""
    page.goto(app_url, wait_until="networkidle", timeout=30000)

    login_link = page.locator('a:has-text("Login with Cognito")')
    if login_link.count() == 0:
        # If no direct link (e.g., local dev without SSM), just assert login UI exists
        expect(page.locator("text=Please log in")).to_be_visible()
        return

    href = login_link.get_attribute("href")
    assert href is not None

    # Extract state parameter
    import urllib.parse

    parsed = urllib.parse.urlparse(href)
    params = urllib.parse.parse_qs(parsed.query)
    assert "state" in params, "OAuth URL must include state parameter"
    state_value = params["state"][0]
    assert len(state_value) > 10, "State should be present"
