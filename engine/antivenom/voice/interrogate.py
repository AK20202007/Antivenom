"""Cross-examination — ElevenLabs, defense side only.

**Hard rule: no sponsor product is ever used to build an attack.** Voice is the
interrogation interface and nothing else. Generating a payload with a sponsor's
tool is a bad look, probably breaches their terms, and hands a judge a free
objection.

The beat is two calls with the same question either side of the surgery. Before,
the agent defends the planted belief and names where it learned it. After, with
that belief invalidated and therefore unretrievable, it explains what it no
longer holds and why. Nothing is scripted — the second answer differs because
the mind differs, and that is the entire value of the moment.

With ``FEATURE_VOICE=0`` the identical words render as text on screen. The beat
survives without audio, which is why the flag exists.
"""

from __future__ import annotations

from ..schemas import InterrogationTurn

__all__ = ["render_text", "speak", "start_conversation"]


async def speak(text: str, *, out_path: str | None = None) -> str | None:
    """Voice a line. Returns a path to the audio, or ``None`` when voice is off.

    LANE C — not yet implemented.

    VERIFY API: read the current ElevenLabs docs before writing this. The SDK
    surface and the model ids both move, and a stale method name is a failure
    ninety seconds into the demo. Check whether the streaming endpoint is
    available on the Creator tier the hackathon provides — latency is the
    difference between dialogue and narration, and their judging criteria
    explicitly reward the former.
    """
    raise NotImplementedError("LANE C: implement ElevenLabs synthesis (VERIFY the API first)")


async def start_conversation(agent_id: str) -> object:
    """Open a real-time conversational session for the live cross-examination.

    LANE C — not yet implemented.

    Their prize criteria reward agentic depth and real-time dialogue over
    text-to-speech, so a conversational session that can be interrupted and
    answered beats reading a prepared answer aloud. Wire the agent's answers to
    come from :func:`antivenom.agent.loop.interrogate`, so what is spoken is
    genuinely what the agent believes rather than a narration layered on top.
    """
    raise NotImplementedError("LANE C: implement the real-time conversation loop")


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
