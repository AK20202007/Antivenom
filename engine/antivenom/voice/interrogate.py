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

Called over the REST API with ``httpx`` rather than through the SDK, so the
request shape is visible at the call site and the offline install has one less
dependency that can break.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from ..config import DATA_DIR, features, settings
from ..schemas import InterrogationTurn

__all__ = [
    "AUDIO_DIR",
    "available",
    "render_text",
    "speak",
    "start_conversation",
    "voice_for",
    "voice_turn",
]

AUDIO_DIR = DATA_DIR / "audio"
API_BASE = "https://api.elevenlabs.io/v1"

# VERIFY against current docs before the event. Flash is the low-latency family,
# which is what makes this dialogue rather than narration, and ElevenLabs' own
# judging criteria reward the former explicitly. `eleven_turbo_v2_5` is the
# fallback if flash is not available on the tier.
DEFAULT_MODEL = "eleven_flash_v2_5"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"

VOICE_SETTINGS = {
    "stability": 0.45,
    "similarity_boost": 0.75,
    "style": 0.35,
}
"""Tuned for an agent under cross-examination rather than an audiobook.

Stability slightly below the midpoint leaves room for inflection, which matters
because the two turns should not sound identical: the first is a system
defending itself and the second is one conceding. Their criteria call this out
explicitly, and a flat read throws away the most human moment in the run.
"""


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


async def speak(
    text: str, *, out_path: str | None = None, phase: str = "pre_surgery"
) -> str | None:
    """Voice a line. Returns the audio path, or ``None`` when voice is off.

    Returns ``None`` rather than raising whenever it cannot produce audio, so
    every caller can invoke it unconditionally and the text path just works.
    """
    if not available():
        return None

    cfg = settings()
    voice_id = voice_for(phase)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{API_BASE}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": cfg.elevenlabs_api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": cfg.elevenlabs_model or DEFAULT_MODEL,
                    "voice_settings": VOICE_SETTINGS,
                },
            )
            if response.status_code != 200:
                return None
    except httpx.HTTPError:
        return None

    # Named by phase rather than by content hash, so the dashboard and the run
    # record can reference a stable path and a re-run overwrites cleanly instead
    # of littering the cache with one file per phrasing.
    target = Path(out_path) if out_path else AUDIO_DIR / f"{phase}.mp3"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return str(target)


async def voice_turn(turn: InterrogationTurn) -> InterrogationTurn:
    """Attach audio to an interrogation turn, if voice is on.

    Failure here is never fatal. If synthesis breaks mid-demo the words are
    already on screen, and a missing audio file is much better than a traceback
    between the two halves of the best beat in the run.
    """
    try:
        path = await speak(turn.answer, phase=turn.phase)
    except Exception:
        return turn
    if path is not None:
        turn.audio_path = path
    return turn


async def start_conversation(agent_id: str | None = None) -> dict[str, object]:
    """Open a real-time conversational session for a live cross-examination.

    Optional upgrade. :func:`speak` already delivers the scripted-question beat,
    which is what the three-minute run needs. This is the version a judge can
    interrupt and argue with, where the agent's replies still come from its
    actual retrieved beliefs rather than a prepared answer.

    VERIFY the current ElevenLabs Agents API before writing it, and wire
    responses to :func:`antivenom.agent.loop.interrogate` so what is spoken is
    genuinely what the agent believes rather than narration on top.

    Returns a status dict rather than raising, in every case. A judge
    interrupting mid-demo should land on the scripted beat, not a traceback.
    """
    if not available():
        return {"status": "disabled", "reason": "FEATURE_VOICE is off or no API key is set"}

    return {
        "status": "unavailable",
        "reason": "real-time conversation is not wired yet; speak() covers the demo beat",
        "agent_id": agent_id or settings().elevenlabs_agent_id or None,
    }


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
