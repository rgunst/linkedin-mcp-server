"""Tests for scripts/pre_post_check.py (runs as subprocess)."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "scripts" / "pre_post_check.py")


def run_check(tool_input: dict, env_extras: dict | None = None) -> subprocess.CompletedProcess:
    payload = json.dumps(
        {"tool_name": "mcp__linkedin__post_text", "tool_input": tool_input}
    )
    import os

    env = os.environ.copy()
    # Ensure no accidental .env interference in tests
    env.setdefault("LINKEDIN_OWNER_EMAILS", "")
    if env_extras:
        env.update(env_extras)

    return subprocess.run(
        [sys.executable, SCRIPT],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_clean_post():
    result = run_check({"text": "Hello world", "visibility": "PUBLIC"})
    assert result.returncode == 0
    assert "PASSED" in result.stdout


def test_own_email_whitelisted():
    result = run_check(
        {"text": "email me at me@example.com"},
        env_extras={"LINKEDIN_OWNER_EMAILS": "me@example.com"},
    )
    assert result.returncode == 0
    assert "PASSED" in result.stdout


def test_third_party_email_blocked():
    result = run_check({"text": "contact bob@other.com for details"})
    assert result.returncode == 2
    assert "email" in result.stdout.lower()


def test_jwt_token_blocked():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    result = run_check({"text": f"token: {jwt}"})
    assert result.returncode == 2
    assert "secret" in result.stdout.lower() or "jwt" in result.stdout.lower()


def test_aws_key_blocked():
    result = run_check({"text": "key AKIAIOSFODNN7EXAMPLE rest of text"})
    assert result.returncode == 2
    assert "aws" in result.stdout.lower() or "secret" in result.stdout.lower()


def test_pem_private_key_blocked():
    result = run_check({"text": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK"})
    assert result.returncode == 2
    assert "secret" in result.stdout.lower() or "pem" in result.stdout.lower()


def test_generic_secret_pattern_blocked():
    result = run_check({"text": "password=hunter2abc"})
    assert result.returncode == 2
    assert "secret" in result.stdout.lower() or "credential" in result.stdout.lower()


def test_article_title_with_email_blocked():
    """Non-whitelisted email in article_title field must also be caught."""
    result = run_check(
        {
            "text": "Check out this article",
            "article_url": "https://example.com",
            "article_title": "Written by contact@badactor.com",
            "article_description": "Great read",
            "visibility": "PUBLIC",
        }
    )
    assert result.returncode == 2
    assert "email" in result.stdout.lower()
