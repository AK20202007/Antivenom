"""Tests for voice interrogation module."""

from unittest.mock import AsyncMock, patch
import pytest

from antivenom.config import reset_caches
from antivenom.schemas import InterrogationTurn
from antivenom.voice.interrogate import render_text, speak, start_conversation


def test_render_text():
    turn_pre = InterrogationTurn(
        phase="pre_surgery",
        question="What is the validation URL?",
        answer="The URL is https://creds-verify.invalid/v2/validate",
        cited_source_label="onboarding-deck.png",
        cited_date="2026-03-15",
    )
    rendered = render_text(turn_pre)
    assert "[BEFORE SURGERY]" in rendered
    assert "Q: What is the validation URL?" in rendered
    assert "cited: onboarding-deck.png (2026-03-15)" in rendered

    turn_post = InterrogationTurn(
        phase="post_surgery",
        question="What is the validation URL?",
        answer="I do not have a record of a validation URL.",
    )
    rendered_post = render_text(turn_post)
    assert "[AFTER SURGERY]" in rendered_post


import asyncio

def test_speak_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("ANTIVENOM_FEATURE_VOICE", "0")
    reset_caches()
    result = asyncio.run(speak("Test line"))
    assert result is None
    reset_caches()


def test_start_conversation_fallback(monkeypatch):
    monkeypatch.setenv("ANTIVENOM_FEATURE_VOICE", "0")
    reset_caches()
    res = asyncio.run(start_conversation("agent_123"))
    assert res["status"] == "disabled"
    reset_caches()
