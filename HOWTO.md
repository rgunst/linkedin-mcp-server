# LinkedIn MCP Server — Setup Guide

A Model Context Protocol (MCP) server that lets Claude Desktop post to LinkedIn on your behalf via OAuth 2.0.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | ≥ 3.11 |
| Claude Desktop | Latest |
| LinkedIn Developer App | — |

### Create a LinkedIn Developer App

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps) and create a new app.
2. Under **Auth**, add `http://localhost:8765/callback` as an **Authorized redirect URL**.
3. Under **Products**, request access to **Sign In with LinkedIn using OpenID Connect** and **Share on LinkedIn**.
4. Copy your **Client ID** and **Client Secret** — you'll need them below.

---

## Clone & Setup

```bash
git clone https://github.com/yourusername/linkedin-mcp-server.git
cd linkedin-mcp-server

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install runtime dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env and fill in your LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET
```

---

## Authentication

Run the OAuth flow once to obtain and save your access token:

```bash
python auth.py
```

What happens:
1. A local HTTP server starts on port 8765 to receive the OAuth callback.
2. Your browser opens the LinkedIn authorization page.
3. After you approve, LinkedIn redirects to `localhost:8765/callback`.
4. The server exchanges the authorization code for an access token.
5. The token is saved to `.linkedin_token` (this file is gitignored).

You only need to do this once. Tokens are valid for approximately 60 days.

---

## Register with Claude Desktop

1. Copy the example config:
   ```bash
   cp claude_desktop_config.example.json claude_desktop_config.json
   ```

2. Edit `claude_desktop_config.json` and replace `$PROJECT_DIR` with the absolute path to this repository:
   ```json
   {
     "mcpServers": {
       "linkedin": {
         "command": "/absolute/path/to/linkedin-mcp-server/.venv/bin/python",
         "args": ["/absolute/path/to/linkedin-mcp-server/server.py"]
       }
     }
   }
   ```

3. Merge this `mcpServers` entry into your Claude Desktop config at:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

4. Restart Claude Desktop. The LinkedIn tools should appear in the tools panel.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `get_profile()` | Returns your user ID, URN, and name |
| `post_text(text, visibility)` | Posts plain text; visibility is `"PUBLIC"` or `"CONNECTIONS"` |
| `post_with_article(text, article_url, article_title, article_description, visibility)` | Posts text with an external link preview |
| `delete_post(post_urn)` | Deletes a post by its URN (e.g. `urn:li:share:1234567890`) |

---

## Renewing Expired Tokens

Tokens expire after ~60 days. To renew:

```bash
source .venv/bin/activate
python auth.py
```

This overwrites `.linkedin_token` with a fresh token. No other changes needed.

---

## Running Tests

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt

# Unit tests (no network required)
pytest tests/test_server.py -v

# OAuth browser flow test (requires Playwright)
playwright install chromium
pytest tests/test_auth.py -v
```

---

## Security Notes

- `.env` and `.linkedin_token` are gitignored — never commit them.
- `claude_desktop_config.json` (which contains absolute local paths) is also gitignored; use `claude_desktop_config.example.json` as the template.
- The server only requests the minimum OAuth scopes: `openid profile w_member_social`.
