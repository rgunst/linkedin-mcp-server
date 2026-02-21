# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**License:** MIT — Copyright (c) 2026 Ronald de Gunst. See [LICENSE](LICENSE).

## Project Overview

A LinkedIn MCP (Model Context Protocol) server that exposes LinkedIn posting capabilities as tools for Claude Desktop. It bridges Claude AI with LinkedIn's REST API via OAuth 2.0 authentication.

## Project Location

```
~/Projects/claude/linkedin-mcp-server/
```

## Setup & Commands

```bash
# Install dependencies (use virtual environment)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time OAuth authentication (opens browser, captures token to .linkedin_token)
python auth.py

# Run the MCP server manually
python server.py

# Run unit tests
pip install -r requirements-dev.txt
pytest tests/test_server.py -v

# Run OAuth browser flow test (requires Playwright)
playwright install chromium
pytest tests/test_auth.py -v

# Run all tests
pytest tests/ -v

# Vulnerability scan
trivy fs --severity HIGH,CRITICAL .
```

The server is normally invoked by Claude Desktop — copy `claude_desktop_config.example.json` to `claude_desktop_config.json`, fill in absolute paths, and merge into `~/Library/Application Support/Claude/claude_desktop_config.json`.

## Authentication

- Copy `.env.example` to `.env` and populate `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` from your LinkedIn Developer App.
- Run `python auth.py` once — it starts a local HTTP server on port 8765, opens a browser for OAuth, and saves the token to `.linkedin_token`.
- Token resolution in `server.py` checks `LINKEDIN_ACCESS_TOKEN` env var first, then falls back to `.linkedin_token` file.
- Tokens expire after ~60 days; re-run `auth.py` to refresh.

## Architecture

Two-file design with clear separation:

- **`auth.py`** — Standalone OAuth 2.0 flow: generates auth URL, spins up a local callback server on port 8765, exchanges code for token, writes `.linkedin_token`.
- **`server.py`** — FastMCP server exposing four tools: `get_profile`, `post_text`, `post_with_article`, `delete_post`. All API calls go to `https://api.linkedin.com/rest` with API version header `LinkedIn-Version: 202601`.

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_profile()` | Returns user ID, URN, and name |
| `post_text(text, visibility)` | Posts plain text; visibility is `"PUBLIC"` or `"CONNECTIONS"` |
| `post_with_article(text, article_url, article_title, article_description, visibility)` | Posts text with external link preview |
| `delete_post(post_urn)` | Deletes a post by URN (e.g. `urn:li:share:1234567890`) |

## Posting Safety Protocol (MANDATORY)

Before calling `post_text` or `post_with_article`:

1. **Always display** the exact post text (and article URL/title if applicable) to
   the user.
2. **Always ask** "Shall I post this to LinkedIn?" and wait for explicit approval.
3. **Never post** content that contains:
   - Email addresses of third parties (your own email from `LINKEDIN_OWNER_EMAILS`
     in `.env` is fine)
   - Phone numbers, credit/debit card numbers, IBANs, or government ID numbers
   - Passwords, API keys, tokens, or any credential material
   - Health, biometric, or other GDPR special-category data of identifiable people
4. If the content violates any rule above, refuse and explain why instead of posting.
5. **Never use parentheses `()`** in post text — LinkedIn's API silently truncates content at the first `(` character.

## LinkedIn API Notes

- All requests require headers: `Authorization: Bearer <token>`, `LinkedIn-Version: 202601`, `X-Restli-Protocol-Version: 2.0.0`
- Post payloads must include `author` (person URN), `lifecycleState: "PUBLISHED"`, and `distribution` object
- Required OAuth scopes: `openid profile w_member_social`
- URNs for delete requests must be URL-encoded

## Secrets Hygiene

Never commit:
- `.env` (credentials)
- `.linkedin_token` (access token)
- `claude_desktop_config.json` (contains absolute local paths)

These are all listed in `.gitignore`.
