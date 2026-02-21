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

## Quick start

**Prerequisites:** Python ≥ 3.11 and a [LinkedIn Developer App](https://www.linkedin.com/developers/apps) with OAuth scopes `openid profile w_member_social`.

```bash
# 1. Clone and set up the virtual environment
git clone https://github.com/rgunst/linkedin-mcp-server.git
cd linkedin-mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Add your LinkedIn credentials
cp .env.example .env
# Edit .env and fill in LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET

# 3. Authenticate once (opens a browser window)
python auth.py

# 4. Register with Claude Desktop
```

Open (or create) `~/Library/Application Support/Claude/claude_desktop_config.json` and add the following, replacing `<absolute-path>` with the full path to your clone (e.g. `/Users/you/Projects/linkedin-mcp-server`):

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

If the file already exists and already has an `"mcpServers"` key, add only the `"linkedin"` block inside it.

Restart Claude Desktop and you should see the LinkedIn tools available.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run unit tests
pytest tests/test_server.py -v

# Run OAuth browser flow test (requires Playwright)
playwright install chromium
pytest tests/test_auth.py -v

# Vulnerability scan
trivy fs --severity HIGH,CRITICAL .
```

## License

MIT — see [LICENSE](LICENSE)
