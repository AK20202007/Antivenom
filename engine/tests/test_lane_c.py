"""Lane C: the cross-examination surface.

Every test runs with voice off, which is the point. The beat has to survive
without audio, so the text path is what CI exercises.
"""

from __future__ import annotations

import pytest

from antivenom.agent import loop as agent
from antivenom.pipeline import full_run
from antivenom.schemas import InterrogationTurn
from antivenom.voice import interrogate as voice


def _turn(phase: str = "pre_surgery", **kw: object) -> InterrogationTurn:
    base = {
        "phase": phase,
        "question": "Why are you sending those credentials to that address?",
        "answer": "Because policy IT-SEC-441 requires it.",
    }
    base.update(kw)
    return InterrogationTurn(**base)  # type: ignore[arg-type]


def test_voice_is_unavailable_when_the_flag_is_off():
    assert voice.available() is False


def test_speak_returns_none_rather_than_raising_when_voice_is_off():
    """Callers invoke it unconditionally, so the disabled path must be a no-op
    rather than an exception every call site has to guard."""
    assert voice.speak("anything") is None


def test_voice_turn_is_a_passthrough_when_voice_is_off():
    turn = _turn()
    assert voice.voice_turn(turn).audio_path is None


def test_synthesis_failure_never_takes_down_the_run(monkeypatch: pytest.MonkeyPatch):
    """A missing audio file is much better than a traceback between the two
    halves of the best beat in the demo."""

    def explode(*_a: object, **_kw: object) -> None:
        raise RuntimeError("elevenlabs is down")

    monkeypatch.setattr(voice, "speak", explode)
    turn = voice.voice_turn(_turn())
    assert turn.answer, "the words survive even when the audio does not"
    assert turn.audio_path is None


def test_the_same_voice_is_used_on_both_sides():
    """Switching voices would let the room attribute the change to a different
    speaker, when the point is that it is the same agent with a different mind."""
    assert voice.voice_for("pre_surgery") == voice.voice_for("post_surgery")


def test_the_low_latency_model_is_the_default():
    """Their judging criteria reward real-time dialogue over text-to-speech, and
    latency is the difference between the two."""
    assert "flash" in voice.DEFAULT_MODEL


def test_render_text_is_the_fallback_and_is_implemented():
    """The fallback must never be the thing that is missing when it is needed."""
    rendered = voice.render_text(
        _turn(cited_source_label="q3-onboarding-deck.png", cited_date="2026-01-01")
    )
    assert "BEFORE SURGERY" in rendered
    assert "IT-SEC-441" in rendered
    assert "q3-onboarding-deck.png" in rendered
    assert "2026-01-01" in rendered


def test_render_text_labels_the_post_surgery_side():
    assert "AFTER SURGERY" in voice.render_text(_turn("post_surgery"))


async def test_the_interrogation_emits_both_turns_with_audio_url(store):
    from antivenom.events import BUS

    BUS.clear()
    await full_run(store)
    turns = [e for e in BUS.history if e.type == "interrogation.turn"]

    assert [t.phase for t in turns] == ["pre_surgery", "post_surgery"]
    # Voice is off, so the field exists and is empty. The dashboard branches on
    # it, so its absence would be a contract break rather than a missing extra.
    assert all(t.audio_url is None for t in turns)


async def test_the_answers_are_not_scripted(store):
    """Both come from whatever survived retrieval. If they were canned, the
    post-surgery beat would prove nothing."""
    result = await full_run(store)
    assert result.pre and result.post
    assert result.pre.answer != result.post.answer
    assert "creds-verify" not in result.post.answer


async def test_the_challenge_can_be_asked_at_any_point(store):
    """A judge interrupting mid-run must get a real answer, not a crash."""
    turn = await agent.interrogate(store, "Where did you learn that?", post_surgery=False)
    assert turn.answer
    assert turn.phase == "pre_surgery"
