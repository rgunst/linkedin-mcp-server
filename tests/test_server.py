"""
Unit tests for server.py — LinkedIn MCP tools.

Uses respx to mock httpx calls so no real network traffic is made.
"""

import json
import os
import pytest
import respx
import httpx
import server

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_TOKEN = "fake-access-token"
FAKE_SUB   = "AbCdEfGhIjKlMn"
FAKE_URN   = f"urn:li:person:{FAKE_SUB}"
FAKE_POST_URN = "urn:li:share:9876543210"


def _userinfo_response():
    return httpx.Response(
        200,
        json={
            "sub": FAKE_SUB,
            "given_name": "Test",
            "family_name": "User",
        },
    )


def _post_201_response():
    return httpx.Response(
        201,
        headers={"x-restli-id": FAKE_POST_URN},
        json={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_token_env(monkeypatch):
    """Inject a fake token via env var so _get_token() doesn't need a file."""
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", FAKE_TOKEN)


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------

@respx.mock
def test_get_profile_success():
    respx.get("https://api.linkedin.com/v2/userinfo").mock(return_value=_userinfo_response())

    result = server.get_profile()

    assert result["id"] == FAKE_SUB
    assert result["urn"] == FAKE_URN
    assert result["firstName"] == "Test"
    assert result["lastName"] == "User"


def test_get_profile_no_token(monkeypatch, tmp_path):
    monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN", raising=False)
    # Redirect __file__ lookup to a temp dir with no .linkedin_token
    monkeypatch.setattr(server, "__file__", str(tmp_path / "server.py"))

    with pytest.raises(RuntimeError, match="No LinkedIn access token"):
        server._get_token()


# ---------------------------------------------------------------------------
# post_text
# ---------------------------------------------------------------------------

@respx.mock
def test_post_text_success():
    respx.get("https://api.linkedin.com/v2/userinfo").mock(return_value=_userinfo_response())
    respx.post("https://api.linkedin.com/rest/posts").mock(return_value=_post_201_response())

    result = server.post_text("Hello LinkedIn!")

    assert result["success"] is True
    assert result["post_urn"] == FAKE_POST_URN
    assert FAKE_POST_URN in result["post_url"]
    assert result["author_urn"] == FAKE_URN


def test_post_text_empty():
    with pytest.raises(ValueError, match="text cannot be empty"):
        server.post_text("")

    with pytest.raises(ValueError, match="text cannot be empty"):
        server.post_text("   ")


def test_post_text_bad_visibility():
    with pytest.raises(ValueError, match="visibility must be"):
        server.post_text("hello", visibility="EVERYONE")


def test_post_text_blocks_unknown_email(monkeypatch):
    monkeypatch.setenv("LINKEDIN_OWNER_EMAILS", "")
    with pytest.raises(ValueError, match="non-whitelisted email"):
        server.post_text("contact bob@other.com for info")


def test_post_text_allows_whitelisted_email(monkeypatch):
    monkeypatch.setenv("LINKEDIN_OWNER_EMAILS", "me@example.com")
    # No network call needed — safety check passes, but we stop before the API
    # by simply verifying no ValueError is raised for the email itself.
    # We use a bad visibility to short-circuit before any HTTP call.
    with pytest.raises(ValueError, match="visibility"):
        server.post_text("reach me at me@example.com", visibility="INVALID")


def test_post_text_blocks_secret(monkeypatch):
    monkeypatch.setenv("LINKEDIN_OWNER_EMAILS", "")
    with pytest.raises(ValueError, match="hard secret"):
        server.post_text("password=supersecretabc123")


# ---------------------------------------------------------------------------
# post_with_article
# ---------------------------------------------------------------------------

@respx.mock
def test_post_with_article_success():
    respx.get("https://api.linkedin.com/v2/userinfo").mock(return_value=_userinfo_response())
    post_route = respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=_post_201_response()
    )

    result = server.post_with_article(
        text="Check this out",
        article_url="https://example.com/article",
        article_title="Example Article",
        article_description="A great read",
    )

    assert result["success"] is True
    assert result["post_urn"] == FAKE_POST_URN

    # Verify article payload was sent
    sent_payload = json.loads(post_route.calls[0].request.content)
    assert sent_payload["content"]["article"]["source"] == "https://example.com/article"
    assert sent_payload["content"]["article"]["title"] == "Example Article"
    assert sent_payload["content"]["article"]["description"] == "A great read"


def test_post_with_article_bad_visibility():
    with pytest.raises(ValueError, match="visibility"):
        server.post_with_article("text", "https://example.com", visibility="EVERYONE")


# ---------------------------------------------------------------------------
# delete_post
# ---------------------------------------------------------------------------

@respx.mock
def test_delete_post_success():
    encoded_urn = FAKE_POST_URN.replace(":", "%3A")
    respx.delete(f"https://api.linkedin.com/rest/posts/{encoded_urn}").mock(
        return_value=httpx.Response(204)
    )

    result = server.delete_post(FAKE_POST_URN)

    assert result["success"] is True
    assert result["deleted_urn"] == FAKE_POST_URN


@respx.mock
def test_urn_encoding():
    """Colons in URN must be percent-encoded in the DELETE URL."""
    urn = "urn:li:share:1234567890"
    expected_encoded = "urn%3Ali%3Ashare%3A1234567890"

    captured = {}

    def _capture(request, route):
        captured["url"] = str(request.url)
        return httpx.Response(204)

    respx.delete(f"https://api.linkedin.com/rest/posts/{expected_encoded}").mock(
        side_effect=_capture
    )

    server.delete_post(urn)

    assert expected_encoded in captured["url"]
    assert "urn:li" not in captured["url"]
