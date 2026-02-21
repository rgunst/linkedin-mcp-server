"""
LinkedIn OAuth 2.0 Helper
Run once to get your access token, which is saved to .linkedin_token

Usage:
    python auth.py

Requires LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in environment
(or a .env file).
"""

import os
import json
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import httpx

# ---------------------------------------------------------------------------
# Load .env if present
# ---------------------------------------------------------------------------
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8765/callback"
SCOPES        = "openid profile w_member_social"

AUTH_URL  = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# ---------------------------------------------------------------------------
# Minimal local callback server
# ---------------------------------------------------------------------------
auth_code   = None
state_check = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = parse_qs(urlparse(self.path).query)

        if "error" in params:
            print(f"\n[ERROR] {params['error'][0]}: {params.get('error_description', [''])[0]}")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Auth failed. Check terminal.</h1>")
            return

        returned_state = params.get("state", [""])[0]
        if returned_state != state_check:
            print("\n[ERROR] State mismatch — possible CSRF.")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>State mismatch.</h1>")
            return

        auth_code = params.get("code", [""])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h1>Auth successful! You can close this tab.</h1>")

    def log_message(self, format, *args):
        pass  # suppress access logs


def run_oauth_flow():
    global state_check

    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit(
            "Missing LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET.\n"
            "Create a .env file or export the vars before running."
        )

    state_check = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "state":         state_check,
        "scope":         SCOPES,
    }

    auth_link = f"{AUTH_URL}?{urlencode(params)}"
    print(f"\nOpening browser for LinkedIn auth...\n{auth_link}\n")
    webbrowser.open(auth_link)

    # Wait for callback
    server = HTTPServer(("localhost", 8765), CallbackHandler)
    print("Waiting for OAuth callback on http://localhost:8765 ...")
    server.handle_request()

    if not auth_code:
        raise SystemExit("No auth code received.")

    # Exchange code for token
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "code":          auth_code,
            "redirect_uri":  REDIRECT_URI,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()

    # Save token
    token_file = os.path.join(os.path.dirname(__file__), ".linkedin_token")
    with open(token_file, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✓ Access token saved to {token_file}")
    print(f"  Expires in: {token_data.get('expires_in', '?')} seconds (~60 days)")
    print("\nYou can now run the MCP server.")


if __name__ == "__main__":
    run_oauth_flow()
