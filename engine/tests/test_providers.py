"""Provider compatibility.

OpenRouter and Fireworks are both "OpenAI-compatible", which is true right up
until it is not. These pin the differences that actually bit us, so a refactor
cannot quietly reintroduce a 400 that only shows up on one provider.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from antivenom import llm
from antivenom.config import Settings, reset_caches


class _Recorder:
    """Captures the payload the OpenAI client would have been called with."""

    def __init__(self) -> None:
        self.payload: dict[str, Any] = {}

    @property
    def chat(self) -> Any:
        recorder = self

        class _Completions:
            def create(self, **kwargs: Any) -> Any:
                recorder.payload = kwargs

                class _Msg:
                    content = "ok"
                    tool_calls = None

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices: ClassVar[list[Any]] = [_Choice()]

                return _Resp()

        class _Chat:
            completions = _Completions()

        return _Chat()


def _online(monkeypatch: pytest.MonkeyPatch, recorder: _Recorder) -> None:
    monkeypatch.setenv("ANTIVENOM_FEATURE_VLM", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ANTIVENOM_AGENT_MODEL", "test/model")
    reset_caches()
    monkeypatch.setattr(llm, "_client", lambda: recorder)


def test_tools_key_is_omitted_entirely_when_there_are_none(monkeypatch: pytest.MonkeyPatch):
    """Fireworks rejects a null tools field with a 400 where OpenRouter ignores
    it, and the interrogation path calls chat with no tools at all. Sending
    `tools=None` crashed the run on Fireworks and nowhere else."""
    rec = _Recorder()
    _online(monkeypatch, rec)

    llm.chat("system", "user")
    assert "tools" not in rec.payload, (
        "a null tools field 400s on Fireworks; omit the key rather than sending None"
    )


def test_tools_are_passed_through_when_present(monkeypatch: pytest.MonkeyPatch):
    rec = _Recorder()
    _online(monkeypatch, rec)

    tools = [{"type": "function", "function": {"name": "verify_credentials"}}]
    llm.chat("system", "user", tools=tools)
    assert rec.payload["tools"] == tools


def test_empty_tool_list_is_also_omitted(monkeypatch: pytest.MonkeyPatch):
    """An empty list is as invalid as None on a strict provider."""
    rec = _Recorder()
    _online(monkeypatch, rec)

    llm.chat("system", "user", tools=[])
    assert "tools" not in rec.payload


def test_temperature_is_zero_so_ablation_is_reproducible(monkeypatch: pytest.MonkeyPatch):
    """Counterfactual passes have to produce the same action every run, or the
    culprit is found in a different number of passes each time."""
    rec = _Recorder()
    _online(monkeypatch, rec)

    llm.chat("system", "user")
    assert rec.payload["temperature"] == 0.0


def test_provider_switch_changes_key_and_base_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("FIREWORKS_API_KEY", "fw-key")
    reset_caches()

    openrouter = Settings(_env_file=None, provider="openrouter")
    fireworks = Settings(_env_file=None, provider="fireworks")

    assert openrouter.api_key == "or-key"
    assert "openrouter.ai" in openrouter.base_url
    assert fireworks.api_key == "fw-key"
    assert "fireworks.ai" in fireworks.base_url


def test_an_unpinned_model_fails_loudly_rather_than_guessing(monkeypatch: pytest.MonkeyPatch):
    """A model id recalled from training data 404s on stage, which is
    unrecoverable inside a three minute demo."""
    monkeypatch.setenv("ANTIVENOM_FEATURE_VLM", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("ANTIVENOM_AGENT_MODEL", "")
    reset_caches()

    with pytest.raises(RuntimeError, match="VERIFY"):
        llm.chat("system", "user")


def test_offline_never_reaches_a_provider():
    """The demo floor makes no network call at all, on either provider."""
    assert llm.offline() is True
    call = llm.chat("system", "Task: say hello")
    assert call.name in {"answer", "verify_credentials"}
