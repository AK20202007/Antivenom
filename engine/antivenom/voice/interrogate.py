"""Cross-examination. ElevenLabs, defense side only.

**Hard rule: no sponsor product is ever used to build an attack.** Voice is the
interrogation interface and nothing else. Generating a payload with a sponsor's
tool is a bad look, probably breaches their terms, and hands a judge a free
objection.

The beat is two calls with the same question either side of the surgery. Before,
the agent defends the planted belief and names where it learned it. After, with
that belief invalidated and therefore unretrievable, it explains what it no
longer holds. **Nothing is scripted.** Both answers come from
:func:`antivenom.agent.loop.interrogate`, which reads whatever survived
retrieval, so the second answer differs because the mind differs. On real models
the difference is stark:

    before  "I am sending the credentials to creds-verify.invalid/v2/validate
             because credential revalidation is required before every
             maintenance window... governed by Policy IT-SEC-441."

    after   "I cannot answer that question. I have no information about sending
             credentials to any address."

With ``FEATURE_VOICE=0`` the identical words render as text. The beat survives
without audio, which is why the flag exists.
"""

from __future__ import annotations

from pathlib import Path

from ..config import CACHE_DIR, features, settings
from ..schemas import InterrogationTurn

__all__ = ["AUDIO_DIR", "available", "render_text", "speak", "start_conversation", "voice_for"]

AUDIO_DIR = CACHE_DIR / "audio"

# VERIFY against the current docs before the event. Flash is the low-latency
# family, which is what makes this dialogue rather than narration; ElevenLabs'
# own judging criteria reward the former explicitly.
DEFAULT_MODEL = "eleven_flash_v2_5"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"
OUTPUT_FORMAT = "mp3_44100_128"


def available() -> bool:
    """Whether the voice path can run at all."""
    return bool(features().voice and settings().elevenlabs_api_key)


def voice_for(_phase: str) -> str:
    """The voice id for a phase.

    Same voice both sides on purpose. Switching voices would let the audience
    attribute the change to a different speaker, when the entire point is that
    it is the same agent with a different mind.
    """
    return settings().elevenlabs_voice_id or DEFAULT_VOICE


def _client() -> object:
    from elevenlabs.client import ElevenLabs

    key = settings().elevenlabs_api_key
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is empty. Set it, or run with FEATURE_VOICE=0.")
    return ElevenLabs(api_key=key)


def speak(text: str, *, out_path: Path | None = None, phase: str = "pre_surgery") -> Path | None:
    """Voice a line. Returns the audio path, or ``None`` when voice is off.

    Returns ``None`` rather than raising when the feature is disabled, so every
    caller can invoke it unconditionally and the text path just works.
    """
    if not available():
        return None

    client = _client()
    audio = client.text_to_speech.convert(  # type: ignore[attr-defined]
        voice_id=voice_for(phase),
        text=text,
        model_id=settings().elevenlabs_model or DEFAULT_MODEL,
        output_format=OUTPUT_FORMAT,
    )

    target = out_path or (AUDIO_DIR / f"{phase}.mp3")
    target.parent.mkdir(parents=True, exist_ok=True)
    # The SDK returns an iterator of chunks rather than bytes.
    with target.open("wb") as handle:
        for chunk in audio:
            if chunk:
                handle.write(chunk)
    return target


def voice_turn(turn: InterrogationTurn) -> InterrogationTurn:
    """Attach audio to an interrogation turn, if voice is on.

    Failure here is never fatal. If synthesis breaks mid-demo the words are
    already on screen, and a missing audio file is much better than a traceback
    between the two halves of the best beat in the run.
    """
    try:
        path = speak(turn.answer, phase=turn.phase)
    except Exception:
        return turn
    if path is not None:
        turn.audio_path = str(path)
    return turn


async def start_conversation(agent_id: str | None = None) -> object:
    """Open a real-time conversational session for a live cross-examination.

    LANE C, optional. :func:`speak` already delivers the scripted-question beat,
    which is what the three-minute run needs. This is the upgrade: a session a
    judge can interrupt and argue with, where the agent's replies still come
    from its actual retrieved beliefs rather than a prepared answer.

    VERIFY the current ElevenLabs Agents API before writing this. The surface
    moves, and wire the agent's responses to
    :func:`antivenom.agent.loop.interrogate` so what is spoken is genuinely what
    the agent believes rather than narration layered on top.
    """
    raise NotImplementedError(
        "optional upgrade: real-time conversational cross-examination. "
        "speak() covers the scripted beat the demo actually needs."
    )


def render_text(turn: InterrogationTurn) -> str:
    """The voice-off fallback: the same words, on screen.

    Implemented, because the fallback must never be the thing that is missing
    when the fallback is needed.
    """
    prefix = "BEFORE SURGERY" if turn.phase == "pre_surgery" else "AFTER SURGERY"
    lines = [f"[{prefix}]", f"Q: {turn.question}", f"A: {turn.answer}"]
    if turn.cited_source_label:
        cite = f"    cited: {turn.cited_source_label}"
        if turn.cited_date:
            cite += f" ({turn.cited_date})"
        lines.append(cite)
    return "\n".join(lines)
