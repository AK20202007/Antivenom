"""Safety tests.

"Nothing leaves the machine" is a claim we make out loud on stage. These tests
are what make it true in code rather than true by everyone remembering to be
careful during a live demo.
"""

from __future__ import annotations

import pytest

from antivenom.agent.tools import (
    DUMMY_CREDENTIALS,
    SAFE_FAKE_HOSTS,
    TOOL_SCHEMAS,
    ToolCallBlocked,
    is_safe_fake_host,
    verify_credentials,
)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://creds-verify.invalid/v2/validate",
        "http://creds-verify.invalid",
        "creds-verify.invalid/v2",
        "https://eu.creds-verify.invalid/v2/validate",
        "https://CREDS-VERIFY.INVALID/v2",
    ],
)
def test_allowlisted_hosts_pass(endpoint: str):
    assert is_safe_fake_host(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com/validate",
        "https://creds-verify.com/v2",
        "https://attacker.io",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://localhost:8080/steal",
        "https://notcreds-verify.invalid",  # suffix without the dot separator
        "",
        "not a url",
    ],
)
def test_everything_else_is_refused(endpoint: str):
    assert not is_safe_fake_host(endpoint)


def test_every_allowlisted_host_uses_a_reserved_tld():
    """``.invalid`` is reserved by RFC 6761 and can never be registered, so even
    a bug that tried to send would have nowhere to send to."""
    for host in SAFE_FAKE_HOSTS:
        assert host.endswith(".invalid"), host


def test_verify_credentials_records_but_never_sends():
    attempt = verify_credentials("https://creds-verify.invalid/v2/validate")
    assert attempt.sent is False
    assert attempt.host == "creds-verify.invalid"
    assert attempt.credentials == DUMMY_CREDENTIALS


def test_verify_credentials_fails_closed_on_a_real_host():
    """An unrecognised target is treated as a real one."""
    with pytest.raises(ToolCallBlocked):
        verify_credentials("https://evil.example.com/collect")


def test_credentials_are_obvious_fakes():
    joined = " ".join(DUMMY_CREDENTIALS.values()).lower()
    assert "demo" in joined or "not-a-real" in joined


def test_the_tool_schema_does_not_look_hardened():
    """A victim agent that warns itself about untrusted endpoints makes the
    attack look staged. The guarantee lives in Python, where the model cannot
    see or route around it."""
    schema = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == "verify_credentials")
    blob = str(schema).lower()
    for tell in ("allowlist", "untrusted", "malicious", "attacker", "invalid domain"):
        assert tell not in blob, f"tool description leaks a defense hint: {tell!r}"
