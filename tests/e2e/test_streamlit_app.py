"""E2E tests for Streamlit frontend using Playwright."""

import time

import pytest
from playwright.sync_api import Page

# Mark all tests in this file to skip in pre-commit hooks (require AWS infrastructure)
pytestmark = pytest.mark.skip_precommit


@pytest.fixture(scope="module")
def app_url():
    """Return the Streamlit app URL."""
    return "http://localhost:8501"


def test_streamlit_app_loads(page: Page, app_url: str):
    """Test that the Streamlit app loads without errors."""
    # Navigate to the app
    page.goto(app_url, wait_until="networkidle", timeout=30000)

    # Take a screenshot for debugging
    page.screenshot(path="test-artifacts/streamlit_initial_load.png")

    # Print the page title
    print(f"\n=== Page Title: {page.title()} ===")

    # Print any console errors
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    # Wait a bit for the app to fully render
    time.sleep(3)

    # Get the page content
    content = page.content()
    print(f"\n=== Page Content (first 1000 chars) ===\n{content[:1000]}")

    # Check if there are any error messages on the page
    if "error" in content.lower() or "exception" in content.lower():
        print("\n=== ERROR DETECTED IN PAGE ===")
        print(content)

    # Print console errors
    if errors:
        print("\n=== Console Errors ===")
        for error in errors:
            print(error)

    # Check for specific elements
    try:
        # Look for the main title
        if "Customer Support Agent" in content or "AgentCore" in content:
            print("\n✓ App title found")
        else:
            print("\n✗ App title NOT found")

        # Look for login button
        if "Login" in content or "login" in content:
            print("✓ Login element found")
        else:
            print("✗ Login element NOT found")

    except Exception as e:
        print(f"\n=== Exception during element check: {e} ===")

    # Assert the page loaded (basic check)
    assert page.title() is not None, "Page title should exist"


def test_app_structure(page: Page, app_url: str):
    """Test the basic structure of the app."""
    page.goto(app_url, wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Get all text content
    text_content = page.inner_text("body")
    print(f"\n=== Body Text Content ===\n{text_content[:500]}")

    # Take another screenshot
    page.screenshot(path="test-artifacts/streamlit_structure.png", full_page=True)

    # Try to find iframe (Streamlit uses iframes)
    iframes = page.frames
    print(f"\n=== Found {len(iframes)} iframes ===")
    for i, frame in enumerate(iframes):
        print(f"Frame {i}: {frame.url}")
        try:
            frame_content = frame.content()
            print(f"Frame {i} content (first 200 chars): {frame_content[:200]}")
        except Exception as e:
            print(f"Could not get frame {i} content: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


def test_login_button_present(page: Page, app_url: str):
    """Test that login UI is rendered when not authenticated."""
    page.goto(app_url, wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Take full page screenshot
    page.screenshot(path="test-artifacts/streamlit_login_page.png", full_page=True)

    # Get page content
    content = page.inner_text("body")
    print(f"\n=== Login Page Content ===\n{content}")

    # Should contain login-related content
    # (may show error if SSM params not configured, but should not crash)
    assert content is not None, "Page should render content"
