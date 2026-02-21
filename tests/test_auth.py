"""
Integration test for auth.py OAuth browser flow using Playwright.

This test:
1. Sets up a mock LinkedIn token endpoint (via respx/httpx)
2. Launches auth.py as a subprocess (which starts the local callback server)
3. Uses Playwright to navigate directly to the callback URL (bypassing real LinkedIn)
4. Verifies .linkedin_token is written with the correct shape
"""

import json
import os
import subprocess
import sys
import time
import tempfile
import shutil
import pytest

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="playwright not installed — run `pip install playwright && playwright install chromium`",
)

AUTH_PORT = 8765
FAKE_STATE = "test-state-value-1234"
FAKE_CODE  = "fake-auth-code-xyz"
FAKE_TOKEN_RESPONSE = {
    "access_token": "fake-access-token-abc123",
    "expires_in": 5183999,
    "token_type": "Bearer",
}


@pytest.fixture
def temp_project_dir(tmp_path):
    """Copy auth.py into a fresh temp dir so .linkedin_token lands there."""
    src = os.path.join(os.path.dirname(__file__), "..", "auth.py")
    shutil.copy(src, tmp_path / "auth.py")
    # Create a minimal .env with dummy credentials
    (tmp_path / ".env").write_text(
        "LINKEDIN_CLIENT_ID=dummy_client_id\n"
        "LINKEDIN_CLIENT_SECRET=dummy_client_secret\n"
    )
    return tmp_path


def _wait_for_port(port: int, timeout: float = 5.0):
    """Block until localhost:port accepts connections or timeout expires."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def test_oauth_flow_writes_token_file(temp_project_dir, monkeypatch):
    """
    Full OAuth flow: auth.py starts callback server → Playwright hits /callback
    with fake code+state → auth.py exchanges code for token (mocked) →
    .linkedin_token file is written with correct shape.
    """
    # We use a custom token endpoint shim: patch TOKEN_URL in auth.py to point
    # at a tiny http server we control. Instead of patching, we start a thread
    # that serves a single POST and returns our fake token JSON.
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    token_received = threading.Event()
    token_server_port = 8766

    class FakeTokenHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps(FAKE_TOKEN_RESPONSE).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            token_received.set()

        def log_message(self, *args):
            pass

    fake_token_server = HTTPServer(("localhost", token_server_port), FakeTokenHandler)
    token_thread = threading.Thread(target=fake_token_server.handle_request, daemon=True)
    token_thread.start()

    # Patch TOKEN_URL and state via env vars understood by a wrapper script
    env = os.environ.copy()
    env["LINKEDIN_CLIENT_ID"] = "dummy_client_id"
    env["LINKEDIN_CLIENT_SECRET"] = "dummy_client_secret"
    # Override TOKEN_URL via a monkey-patch env var (we'll use a wrapper approach)
    # Since auth.py doesn't read TOKEN_URL from env, we patch it in-process instead.
    # For subprocess isolation we write a thin wrapper that patches before importing.

    wrapper = temp_project_dir / "run_auth.py"
    wrapper.write_text(
        f"""
# Patch secrets.token_urlsafe before auth.py uses it so state_check is predictable
import secrets
secrets.token_urlsafe = lambda n=16: "{FAKE_STATE}"

# Suppress browser open
import webbrowser
webbrowser.open = lambda url: None

import auth
auth.TOKEN_URL = "http://localhost:{token_server_port}/token"

auth.run_oauth_flow()
"""
    )

    proc = subprocess.Popen(
        [sys.executable, str(wrapper)],
        cwd=str(temp_project_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for the callback server to be ready
        assert _wait_for_port(AUTH_PORT, timeout=8), \
            "auth.py callback server did not start in time"

        # Use Playwright to hit the callback URL directly (simulating LinkedIn redirect)
        callback_url = (
            f"http://localhost:{AUTH_PORT}/callback"
            f"?code={FAKE_CODE}&state={FAKE_STATE}"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(callback_url)
            # Page should show success message
            page.wait_for_selector("h1", timeout=5000)
            heading = page.locator("h1").inner_text()
            browser.close()

        assert "successful" in heading.lower(), f"Unexpected page: {heading}"

        # Wait for token exchange to complete
        proc.wait(timeout=10)
        token_received.wait(timeout=5)

        # Verify .linkedin_token was written
        token_file = temp_project_dir / ".linkedin_token"
        assert token_file.exists(), ".linkedin_token was not created"

        data = json.loads(token_file.read_text())
        assert data.get("access_token") == FAKE_TOKEN_RESPONSE["access_token"]
        assert "expires_in" in data

    finally:
        proc.kill()
        fake_token_server.server_close()
