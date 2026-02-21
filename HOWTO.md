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
# Edit .env and fill in LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET,
# and LINKEDIN_OWNER_EMAILS (comma-separated emails safe to appear in posts)
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

   > **Windows:** use `.venv\Scripts\python.exe` — for example:
   > `"command": "C:\\Users\\you\\Projects\\linkedin-mcp-server\\.venv\\Scripts\\python.exe"`

3. Merge this `mcpServers` entry into your Claude Desktop config at:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

4. Restart Claude Desktop. The LinkedIn tools should appear in the tools panel.

---

## Safety & GDPR Compliance

Two guards run automatically before any post is sent:

1. **Approval gate** — Claude is instructed (via `CLAUDE.md`) to always show you the full post text and wait for your explicit confirmation before calling a posting tool.
2. **PreToolUse hook** — `scripts/pre_post_check.py` runs before every `post_text` / `post_with_article` call and blocks the request if it detects:
   - Email addresses not listed in `LINKEDIN_OWNER_EMAILS`
   - JWT tokens, AWS access keys, or PEM private keys
   - Generic credential patterns (`password=…`, `api_key=…`, etc.)

The hook is wired up in `.claude/settings.json` and activates automatically for anyone using Claude Code with this project — no extra configuration needed beyond the standard venv setup (`pip install -r requirements.txt`). The hook uses `.venv/bin/python` so it always runs with the project's dependencies available.

To whitelist your own email address(es), add them to `.env`:

```
LINKEDIN_OWNER_EMAILS=you@example.com,alias@example.com
```

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
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python auth.py
```

This overwrites `.linkedin_token` with a fresh token. No other changes needed.

---

## Running Tests

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# All unit tests (server, safety hook, OAuth flow)
pytest tests/ -v

# OAuth browser flow test requires Playwright (already installed if test_auth passes)
python -m playwright install chromium
pytest tests/test_auth.py -v

# Manual smoke-test the safety hook
echo '{"tool_name":"mcp__linkedin__post_text","tool_input":{"text":"Hello world","visibility":"PUBLIC"}}' \
  | python scripts/pre_post_check.py
```

---

## Security Notes

- `.env` and `.linkedin_token` are gitignored — never commit them.
- `claude_desktop_config.json` (which contains absolute local paths) is also gitignored; use `claude_desktop_config.example.json` as the template.
- The server only requests the minimum OAuth scopes: `openid profile w_member_social`.
- `.linkedin_token` is written with `0600` permissions (owner read/write only) on macOS/Linux.
- The PreToolUse hook in `.claude/settings.json` acts as a backstop against accidental PII or secret leakage in posts — see [Safety & GDPR Compliance](#safety--gdpr-compliance) above.
