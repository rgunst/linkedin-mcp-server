# linkedin-mcp-server

![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

MCP server that gives Claude Desktop the ability to post, manage, and delete LinkedIn updates via OAuth 2.0.

## How it works

`auth.py` runs a one-time OAuth 2.0 flow — it opens a browser, captures the LinkedIn access token, and writes it to `.linkedin_token`. `server.py` is a [FastMCP](https://github.com/jlowin/fastmcp) server that reads that token and exposes four tools to Claude Desktop. All API calls target LinkedIn's REST API (`https://api.linkedin.com/rest`) with API version `202601`.

## Tools

| Tool | Description |
|------|-------------|
| `get_profile()` | Returns your LinkedIn user ID, URN, and display name |
| `post_text(text, visibility)` | Posts plain text; visibility is `"PUBLIC"` or `"CONNECTIONS"` |
| `post_with_article(text, article_url, article_title, article_description, visibility)` | Posts text with an external link preview card |
| `delete_post(post_urn)` | Deletes a post by URN (e.g. `urn:li:share:1234567890`) |

## Safety & GDPR compliance

Before any post is sent, two complementary guards run automatically:

1. **Approval gate (CLAUDE.md)** — Claude is instructed to always display the full post text and wait for your explicit "yes" before calling a posting tool.
2. **PreToolUse hook (`scripts/pre_post_check.py`)** — A lightweight script that runs before every `post_text` / `post_with_article` call and blocks the request if it finds:
   - Email addresses not in your `LINKEDIN_OWNER_EMAILS` whitelist
   - JWT tokens, AWS access keys, or PEM private keys
   - Generic credential assignments (`password=…`, `api_key=…`, etc.)

The hook is configured in `.claude/settings.json` and is active for everyone who opens this repo in Claude Code.

To whitelist your own email address(es), add them to `.env`:

```
LINKEDIN_OWNER_EMAILS=you@example.com,alias@example.com
```

## Quick start

**Prerequisites:** Python ≥ 3.11 and a [LinkedIn Developer App](https://www.linkedin.com/developers/apps) with OAuth scopes `openid profile w_member_social`.

```bash
# 1. Clone and set up the virtual environment
git clone https://github.com/rgunst/linkedin-mcp-server.git
cd linkedin-mcp-server
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Add your LinkedIn credentials
cp .env.example .env
# Edit .env and fill in LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET,
# and LINKEDIN_OWNER_EMAILS (comma-separated emails safe to include in posts)

# 3. Authenticate once (opens a browser window)
python auth.py

# 4. Register with Claude Desktop
```

Open (or create) the Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Replace `<absolute-path>` with the full path to your clone:

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "<absolute-path>/.venv/bin/python",
      "args": ["<absolute-path>/server.py"]
    }
  }
}
```

> **Windows:** use `<absolute-path>\.venv\Scripts\python.exe` for the `command` value.

If the file already exists and already has an `"mcpServers"` key, add only the `"linkedin"` block inside it.

> **Note on credentials:** `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` belong in `.env` only — they are used by `auth.py` during the one-time OAuth flow and are never read by `server.py`. The Claude Desktop config needs no secrets because the server reads the access token directly from `.linkedin_token`.

Restart Claude Desktop and you should see the LinkedIn tools available.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# Run all tests (server, auth, pre-post safety hook)
pytest tests/ -v

# Run OAuth browser flow test (requires Playwright)
python -m playwright install chromium
pytest tests/test_auth.py -v

# Vulnerability scan
trivy fs --severity HIGH,CRITICAL .

# Manual smoke-test the safety hook
echo '{"tool_name":"mcp__linkedin__post_text","tool_input":{"text":"Hello world","visibility":"PUBLIC"}}' \
  | python scripts/pre_post_check.py
```

> **Claude Code users:** This repository includes a `CLAUDE.md` that is
> automatically loaded by Claude Code as project instructions. As with any
> third-party repository, review `CLAUDE.md` before running Claude Code here —
> a malicious file could contain prompt-injection instructions that direct
> Claude to take unintended actions.

## License

MIT — see [LICENSE](LICENSE)
