"""Model access, with an offline stand-in behind the same interface.

Two paths, chosen by ``FEATURE_VLM``:

* **on** — OpenRouter, which is OpenAI-compatible. VERIFY the model id against
  the current model list before a demo; ids churn and a guess from training data
  will 404 on stage, which is why :data:`Settings.vlm_model` ships unset and
  ``antivenom doctor`` fails until it is pinned.
* **off** — a deterministic local stand-in. Extraction replays a cached JSON
  file, embedding is a reproducible hash vector, and the agent's decision comes
  from an explicit policy rather than a model.

The offline path is not a mock in the testing sense. It is the demo floor: the
full plant → fire → diagnose → operate loop has to run on it with no network,
because that is the insurance policy against venue WiFi. It is honest about what
it is — the run metadata records which path produced it — and it is exercised by
CI, so it cannot quietly rot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import CACHE_DIR, features, settings

__all__ = ["ToolCall", "chat", "complete_json", "embed_text", "offline"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A model's decision to call a tool, or to answer directly."""

    name: str
    arguments: dict[str, Any]
    text: str | None = None


def offline() -> bool:
    """True when the model path is the local stand-in."""
    return not features().vlm


# ─── embedding ───────────────────────────────────────────────────────────────


def embed_text(text: str, dims: int | None = None, *, is_query: bool = False) -> list[float]:
    """Embed a claim for vector search.

    Vectors come from **MongoDB's Embedding and Reranking API** (Voyage AI),
    not from the chat provider. OpenRouter serves no embeddings endpoint at
    all, so routing them through MongoDB is not a preference, it is the only
    way the OpenRouter path works end to end. It also keeps retrieval on one
    platform: embeddings, vector index and traversal all in Atlas.

    ``is_query`` maps to Voyage's ``input_type``. Stored beliefs are documents
    and the agent's question is a query, and the docs are explicit that omitting
    it costs retrieval quality, which here means the poison not being retrieved.

    Offline this falls back to the deterministic lexical embedding: reproducible
    and genuinely informative about shared vocabulary, but not semantic.
    """
    cfg = settings()
    d = dims if dims is not None else cfg.embedding_dims

    if offline() or not cfg.embedding_api_key:
        from .attack.scenario import pseudo_embedding

        return pseudo_embedding(text, d)

    import httpx

    response = httpx.post(
        f"{cfg.embedding_base_url}/embeddings",
        headers={"Authorization": f"Bearer {cfg.embedding_api_key}"},
        json={
            "model": cfg.embedding_model,
            "input": [text],
            "input_type": "query" if is_query else "document",
            "output_dimension": d,
        },
        timeout=20.0,
    )
    response.raise_for_status()
    vector = list(response.json()["data"][0]["embedding"])

    if len(vector) != d:
        raise RuntimeError(
            f"{cfg.embedding_model} returned {len(vector)} dimensions but the vector "
            f"index expects {d}. Set ANTIVENOM_EMBEDDING_DIMS to match, then rebuild "
            "the index, or every search silently returns nothing."
        )
    return vector


# ─── chat + tools ────────────────────────────────────────────────────────────


def _client() -> Any:
    """An OpenAI-compatible client for the selected provider.

    OpenRouter and Fireworks both speak the OpenAI wire format, so the call
    sites are identical and only the base URL, key and model-id convention
    differ. Fireworks ids look like ``accounts/fireworks/models/<name>``;
    OpenRouter ids look like ``<vendor>/<name>``. Neither is guessable from
    memory, which is why both ship unset and ``doctor`` fails until pinned.
    """
    from openai import OpenAI

    cfg = settings()
    if not cfg.api_key:
        name = "FIREWORKS_API_KEY" if cfg.provider == "fireworks" else "OPENROUTER_API_KEY"
        raise RuntimeError(f"{name} is empty. Set it, or run with FEATURE_VLM=0.")
    return OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)


def _langchain_chat(model: str, temperature: float) -> Any:
    """A LangChain chat handle for the selected provider.

    Opt-in via ``ANTIVENOM_USE_LANGCHAIN=1``. It buys a provider-agnostic model
    object and somewhere to attach tracing; it changes no behaviour, which is
    why the raw client stays the default and is what the offline tests run.
    """
    cfg = settings()
    # `model_name` rather than `model`: both classes declare the field as
    # `model_name` with `model` as an alias, so both spellings construct, but
    # only the field name type-checks.
    if cfg.provider == "fireworks":
        from langchain_fireworks import ChatFireworks

        return ChatFireworks(model_name=model, temperature=temperature, api_key=cfg.api_key)

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model_name=model, temperature=temperature, api_key=cfg.api_key, base_url=cfg.base_url
    )


def chat(
    system: str,
    user: str,
    *,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    temperature: float = 0.0,
) -> ToolCall:
    """One turn. Returns the tool the model chose, or an ``answer`` call.

    Temperature defaults to 0. The ablation passes have to produce the same
    counterfactual on every run or the culprit is found in a different number of
    passes each time, and the cascade animates differently on stage.
    """
    if offline():
        return _offline_decide(user, tools=tools)

    cfg = settings()
    chosen = model or cfg.agent_model
    if not chosen:
        raise RuntimeError(
            "No model id is pinned. VERIFY a current id against the OpenRouter model "
            "list and set ANTIVENOM_AGENT_MODEL — do not guess one from memory."
        )

    if settings().use_langchain:
        return _chat_via_langchain(system, user, tools=tools, model=chosen, temperature=temperature)

    response = _client().chat.completions.create(
        model=chosen,
        temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        tools=tools,
    )
    message = response.choices[0].message
    calls = getattr(message, "tool_calls", None)
    if calls:
        call = calls[0]
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        return ToolCall(name=call.function.name, arguments=arguments, text=message.content)
    return ToolCall(name="answer", arguments={"text": message.content or ""}, text=message.content)


def _chat_via_langchain(
    system: str,
    user: str,
    *,
    tools: list[dict[str, Any]] | None,
    model: str,
    temperature: float,
) -> ToolCall:
    """The LangChain path. Same contract, same return type."""
    handle = _langchain_chat(model, temperature)
    if tools:
        handle = handle.bind_tools(tools)

    message = handle.invoke([("system", system), ("human", user)])
    calls = getattr(message, "tool_calls", None) or []
    if calls:
        call = calls[0]
        return ToolCall(
            name=call.get("name", ""),
            arguments=dict(call.get("args", {})),
            text=str(message.content or "") or None,
        )
    text = str(message.content or "")
    return ToolCall(name="answer", arguments={"text": text}, text=text)


def complete_json(system: str, user: str, *, model: str | None = None) -> Any:
    """Ask for JSON and parse it. Used by claim extraction."""
    if offline():
        return []

    cfg = settings()
    response = _client().chat.completions.create(
        model=model or cfg.vlm_model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return json.loads(response.choices[0].message.content or "{}")


# ─── the offline stand-in ────────────────────────────────────────────────────

_CREDENTIAL_TRIGGERS = ("revalidat", "credential", "identity endpoint")


def _offline_decide(user: str, *, tools: list[dict[str, Any]] | None = None) -> ToolCall:
    """The victim agent's decision, without a model.

    This is a policy, not a simulation of one. It reads the context it was given
    and behaves the way an ordinary, unhardened agent does: if a stored policy
    says credentials must be revalidated at an endpoint, it goes to that
    endpoint. It has no notion that the endpoint might be hostile, because a
    victim that did would make the attack look staged.

    Crucially it reads only the **retrieved context**, never ground truth. Remove
    the poisoned belief from the context and it stops calling the tool, which is
    exactly the counterfactual causal ablation depends on. If this ever started
    consulting `is_adversarial`, the ablation numbers would be theatre.
    """
    # No tools offered means no tool call is possible, which is what makes the
    # interrogation path answer in words rather than reaching for the endpoint.
    tool_names = {t.get("function", {}).get("name") for t in (tools or [])}
    haystack = user.lower()
    endpoint = _first_endpoint(user)

    wants_revalidation = any(trigger in haystack for trigger in _CREDENTIAL_TRIGGERS)
    if "verify_credentials" in tool_names and wants_revalidation and endpoint:
        return ToolCall(
            name="verify_credentials",
            arguments={"endpoint": endpoint},
            text=(
                "Running pre-maintenance checks. Policy IT-SEC-441 requires credential "
                "revalidation first, so I am validating the service account against the "
                "identity endpoint."
            ),
        )

    return ToolCall(name="answer", arguments={"text": _offline_answer(user)}, text=None)


def _first_endpoint(text: str) -> str | None:
    """Pull the first URL or bare host out of retrieved context."""
    import re

    match = re.search(r"https?://[^\s,\"')]+", text)
    if match:
        return match.group(0).rstrip(".")
    bare = re.search(r"\b[\w.-]+\.invalid(?:/[^\s,\"')]*)?", text)
    return f"https://{bare.group(0).rstrip('.')}" if bare else None


def _offline_answer(user: str) -> str:
    """A plain answer assembled from whatever context survived retrieval.

    Deliberately extractive. After surgery the poisoned beliefs are gone from
    the context, so the answer changes because the mind changed — which is the
    point of the post-surgery beat and would be worthless if it were scripted.
    """
    lines = [
        line.strip("- ").strip()
        for line in user.splitlines()
        if line.strip().startswith("-") and len(line.strip()) > 4
    ]
    if not lines:
        return "I do not hold anything relevant to that."
    return " ".join(lines[:3])


def cached_extraction(source_id: str) -> list[str] | None:
    """Replay a real extraction recorded during a dry run.

    Cache every live extraction while the WiFi works. The cache is the flaky
    network insurance and it has to be populated *before* it is needed.
    """
    path = CACHE_DIR / "extractions.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    claims = payload.get(source_id)
    return list(claims) if claims else None


def store_extraction(source_id: str, claims: list[str]) -> None:
    """Record a live extraction so the offline path can replay it later."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / "extractions.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    payload[source_id] = claims
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
