#!/usr/bin/env python3
"""
PreToolUse hook: scans LinkedIn post content for PII and hard secrets.

Reads JSON from stdin:
  { "tool_name": "...", "tool_input": { "text": "...", ... } }

Exits 0 (allow) or 2 (block).
"""

import json
import os
import re
import sys
from pathlib import Path

# --- helpers -----------------------------------------------------------

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SECRET_PATTERNS = [
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "JWT token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"-----BEGIN .*PRIVATE KEY-----"), "PEM private key"),
    (
        re.compile(r"(?i)(api_key|secret|password|token|passwd)\s*[=:]\s*\S{8,}"),
        "credential assignment",
    ),
]


def load_owner_emails() -> set[str]:
    """Return lowercased whitelisted email addresses from LINKEDIN_OWNER_EMAILS."""
    # Prefer env var (makes testing easy), then load .env file.
    raw = os.environ.get("LINKEDIN_OWNER_EMAILS", "")
    if not raw:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            try:
                from dotenv import dotenv_values  # type: ignore

                cfg = dotenv_values(env_path)
                raw = cfg.get("LINKEDIN_OWNER_EMAILS", "")
            except ImportError:
                pass
    return {addr.strip().lower() for addr in raw.split(",") if addr.strip()}


def scan(text: str, owner_emails: set[str]) -> list[str]:
    """Return a list of human-readable block reasons (empty = clean)."""
    reasons: list[str] = []

    # Email check
    found = {m.lower() for m in EMAIL_RE.findall(text)}
    unknown = found - owner_emails
    if unknown:
        reasons.append(
            f"Non-whitelisted email address(es) detected: {', '.join(sorted(unknown))}. "
            "Add your own addresses to LINKEDIN_OWNER_EMAILS in .env if intentional."
        )

    # Hard-secret checks
    for pattern, label in SECRET_PATTERNS:
        if pattern.search(text):
            reasons.append(f"Possible hard secret detected ({label}).")

    return reasons


# --- main --------------------------------------------------------------


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"BLOCKED: could not parse hook JSON — {exc}", file=sys.stderr)
        sys.exit(2)

    tool_input = payload.get("tool_input", {})
    combined = " ".join(
        str(tool_input.get(field, ""))
        for field in ("text", "article_title", "article_description", "article_url")
    )

    owner_emails = load_owner_emails()
    reasons = scan(combined, owner_emails)

    if reasons:
        print("BLOCKED: post contains sensitive content.")
        for reason in reasons:
            print(f"  - {reason}")
        sys.exit(2)

    print("PASSED: no PII or secrets detected.")
    sys.exit(0)


if __name__ == "__main__":
    main()
