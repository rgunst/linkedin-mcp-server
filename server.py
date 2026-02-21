"""
LinkedIn MCP Server
Posts content to LinkedIn personal profile via the LinkedIn REST API.

Setup:
  pip install -r requirements.txt
  python auth.py          # one-time OAuth flow to get access token
  python server.py        # or register with Claude Desktop
"""

import os
import re
import json
import httpx
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
LINKEDIN_VERSION  = "202601"  # Fix: 202501 is not a valid/released version

# ---------------------------------------------------------------------------
# Safety scanner (enforced at the MCP layer so all clients are protected)
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_SECRET_PATTERNS = [
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "JWT token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"-----BEGIN .*PRIVATE KEY-----"), "PEM private key"),
    (re.compile(r"(?i)(api_key|secret|password|token|passwd)\s*[=:]\s*\S{8,}"), "credential assignment"),
]


def _load_owner_emails() -> set:
    raw = os.environ.get("LINKEDIN_OWNER_EMAILS", "")
    if not raw:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            try:
                from dotenv import dotenv_values
                raw = dotenv_values(env_path).get("LINKEDIN_OWNER_EMAILS", "")
            except ImportError:
                pass
    return {addr.strip().lower() for addr in raw.split(",") if addr.strip()}


def _safety_check(*fields: str) -> None:
    """Raise ValueError if any field contains non-whitelisted emails or hard secrets."""
    combined = " ".join(fields)
    owner_emails = _load_owner_emails()

    found_emails = {m.lower() for m in _EMAIL_RE.findall(combined)}
    unknown = found_emails - owner_emails
    if unknown:
        raise ValueError(
            f"Post blocked: non-whitelisted email address(es) detected: "
            f"{', '.join(sorted(unknown))}. "
            "Add your own addresses to LINKEDIN_OWNER_EMAILS in .env if intentional."
        )

    for pattern, label in _SECRET_PATTERNS:
        if pattern.search(combined):
            raise ValueError(f"Post blocked: possible hard secret detected ({label}).")

def _get_token() -> str:
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        token_file = os.path.join(os.path.dirname(__file__), ".linkedin_token")
        if os.path.exists(token_file):
            with open(token_file) as f:
                data = json.load(f)
                token = data.get("access_token")
    if not token:
        raise RuntimeError(
            "No LinkedIn access token found. "
            "Run `python auth.py` or set LINKEDIN_ACCESS_TOKEN env var."
        )
    return token

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

def _get_profile(token: str) -> dict:
    """Fetch profile using an already-resolved token (avoids duplicate token lookups)."""
    # /v2/userinfo works with openid+profile scopes; /rest/me requires partner API access
    resp = httpx.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    person_id = data.get("sub")
    return {
        "id": person_id,
        "urn": f"urn:li:person:{person_id}",
        "firstName": data.get("given_name"),
        "lastName": data.get("family_name"),
    }

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP("linkedin")


@mcp.tool()
def get_profile() -> dict:
    """Get the authenticated LinkedIn user's profile (name + person URN)."""
    token = _get_token()
    return _get_profile(token)


@mcp.tool()
def post_text(text: str, visibility: str = "PUBLIC") -> dict:
    """
    Post a text update to your LinkedIn personal profile.

    Args:
        text:       The content to post (max ~3000 chars recommended).
        visibility: "PUBLIC" (default) or "CONNECTIONS".

    Returns:
        dict with post_id and post_url.
    """
    if not text or not text.strip():
        raise ValueError("text cannot be empty")

    if visibility not in ("PUBLIC", "CONNECTIONS"):
        raise ValueError("visibility must be 'PUBLIC' or 'CONNECTIONS'")

    _safety_check(text)

    token   = _get_token()
    profile = _get_profile(token)
    author  = profile["urn"]

    payload = {
        "author": author,
        "commentary": text.strip(),
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    resp = httpx.post(
        f"{LINKEDIN_API_BASE}/posts",
        headers=_headers(token),
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()

    post_urn = resp.headers.get("x-restli-id", "")
    return {
        "success": True,
        "post_urn": post_urn,
        "post_url": f"https://www.linkedin.com/feed/update/{post_urn}/",
        "author_urn": author,
    }


@mcp.tool()
def post_with_article(
    text: str,
    article_url: str,
    article_title: str = "",
    article_description: str = "",
    visibility: str = "PUBLIC",
) -> dict:
    """
    Post a LinkedIn update with an external article/link.

    Args:
        text:                Commentary text for the post.
        article_url:         URL of the article to share.
        article_title:       Title shown in the link preview (optional).
        article_description: Description shown in the link preview (optional).
        visibility:          "PUBLIC" or "CONNECTIONS".

    Returns:
        dict with post_id and post_url.
    """
    if not text or not article_url:
        raise ValueError("text and article_url are required")

    if visibility not in ("PUBLIC", "CONNECTIONS"):
        raise ValueError("visibility must be 'PUBLIC' or 'CONNECTIONS'")

    _safety_check(text, article_title, article_description)

    token   = _get_token()
    profile = _get_profile(token)
    author  = profile["urn"]

    # Fix: removed unused `content` variable; payload uses article directly
    payload = {
        "author": author,
        "commentary": text.strip(),
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "article": {
                "source": article_url,
                "title": article_title or "",
                "description": article_description or "",
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    resp = httpx.post(
        f"{LINKEDIN_API_BASE}/posts",
        headers=_headers(token),
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()

    post_urn = resp.headers.get("x-restli-id", "")
    return {
        "success": True,
        "post_urn": post_urn,
        "post_url": f"https://www.linkedin.com/feed/update/{post_urn}/",
        "author_urn": author,
    }


@mcp.tool()
def delete_post(post_urn: str) -> dict:
    """
    Delete a LinkedIn post by its URN.

    Args:
        post_urn: The post URN (e.g. urn:li:share:1234567890).
    """
    token = _get_token()
    encoded = post_urn.replace(":", "%3A")
    resp = httpx.delete(
        f"{LINKEDIN_API_BASE}/posts/{encoded}",
        headers=_headers(token),
        timeout=10,
    )
    resp.raise_for_status()
    return {"success": True, "deleted_urn": post_urn}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
