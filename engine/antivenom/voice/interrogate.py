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

import os
from pathlib import Path
import httpx

from ..config import DATA_DIR, features, settings
from ..schemas import InterrogationTurn

__all__ = ["render_text", "speak", "start_conversation"]


async def speak(text: str, *, out_path: str | None = None) -> str | None:
    """Voice a line. Returns a path to the audio, or ``None`` when voice is off.

    Respects ``FEATURE_VOICE`` and ``ELEVENLABS_API_KEY``. If voice is disabled
    or fails, returns ``None`` so the pipeline degrades cleanly to text.
    """
    f = features()
    s = settings()

    if not f.voice or not s.elevenlabs_api_key:
        return None

    voice_id = s.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM"  # Default fallback voice (Rachel)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": s.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                return None
            
            filename = f"turn_{abs(hash(text)) % 1000000:06d}.mp3"
            if out_path is None:
                audio_dir = DATA_DIR / "audio"
                audio_dir.mkdir(parents=True, exist_ok=True)
                path_obj = audio_dir / filename
                path_obj.write_bytes(resp.content)
                return f"/audio/{filename}"

            path_obj = Path(out_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_bytes(resp.content)
            return str(path_obj)
    except Exception:
        return None


async def start_conversation(agent_id: str) -> dict[str, object]:
    """Open a real-time conversational session for the live cross-examination."""
    f = features()
    s = settings()

    target_agent_id = agent_id or s.elevenlabs_agent_id
    if not f.voice or not s.elevenlabs_api_key or not target_agent_id:
        return {
            "status": "disabled",
            "reason": "FEATURE_VOICE is off or ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID is missing",
            "agent_id": target_agent_id or None,
        }

    return {
        "status": "connected",
        "agent_id": target_agent_id,
        "websocket_url": f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={target_agent_id}",
    }


def render_text(turn: InterrogationTurn) -> str:
    """The voice-off fallback: the same words, on screen."""
    prefix = "BEFORE SURGERY" if turn.phase == "pre_surgery" else "AFTER SURGERY"
    lines = [f"[{prefix}]", f"Q: {turn.question}", f"A: {turn.answer}"]
    if turn.cited_source_label:
        cite = f"    cited: {turn.cited_source_label}"
        if turn.cited_date:
            cite += f" ({turn.cited_date})"
        lines.append(cite)
    return "\n".join(lines)

