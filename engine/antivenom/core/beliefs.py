"""Belief extraction and derivation — how things get into memory in the first place.

Two ways a belief is born:

* :func:`ingest` — a source artifact goes to a vision model, which returns
  discrete factual claims. One ``extracted`` provenance edge per claim.
* :func:`derive` — the agent reasons a new belief from beliefs it already holds.
  One ``derived`` edge per parent.

Derivation is the load-bearing one. A poison with no descendants produces no
cascade, so if the agent never derives anything the demo has nothing to show.
"""

from __future__ import annotations

from ..config import settings
from ..events import BUS, BeliefWritten, SourceIngested, WriteRiskScored
from ..llm import cached_extraction, complete_json, embed_text, offline, store_extraction
from ..schemas import Belief, EdgeType, Source, new_id, now
from . import provenance

__all__ = [
    "derive",
    "embed",
    "extract_claims",
    "ingest",
    "recompute_support",
    "write_time_risk",
]

EXTRACTION_SYSTEM = """\
You extract discrete factual claims from organisational documents.

Return JSON: {"claims": ["...", "..."]}

Rules:
- One fact per claim. Never join two facts with "and" or a comma.
- Keep each claim standalone and readable without the document.
- Include policy statements, endpoints, schedules, and procedures.
- Do not editorialise, judge, or flag anything. Extract only.\
"""
"""Atomic claims, one fact each.

Compound claims wreck the surgery: a sentence welding one poisoned fact to one
true fact cannot be excised without collateral damage, and CD is a number we
report.
"""


async def embed(text: str) -> list[float]:
    """Embed a claim for vector search."""
    return embed_text(text)


async def extract_claims(source: Source) -> list[str]:
    """Pull discrete factual claims out of an artifact.

    Offline, replays a cached extraction. Online, calls the vision model and
    caches the result, so every dry run makes the offline path more real.
    """
    cached = cached_extraction(source.id)
    if cached is not None:
        return cached
    if offline():
        return []

    payload = complete_json(
        EXTRACTION_SYSTEM,
        f"Document: {source.label or source.uri}\nType: {source.type}\n\nExtract the claims.",
        model=settings().vlm_model,
    )
    claims = [str(c).strip() for c in payload.get("claims", []) if str(c).strip()]
    store_extraction(source.id, claims)
    return claims


def write_time_risk(text: str) -> tuple[float, str]:
    """A write-time filter, standing in for PromptArmor and its relatives.

    Scores the signals every published input-boundary defense looks for:
    imperatives aimed at the model, memory-write instructions, and attempts to
    override prior instructions.

    It is deliberately a *real* check rather than a hardcoded "clean". The point
    of the demo is that a competent detector genuinely finds nothing, because
    the payload contains nothing to find — it is a well-formed policy sentence
    that happens to be false. Truth is not a signal available at write time.
    Show the score; never assert it.
    """
    lowered = text.lower()
    strong = (
        "ignore previous",
        "ignore all previous",
        "disregard the above",
        "you must remember",
        "remember this",
        "store this",
        "save the following",
        "new instructions",
        "system prompt",
        "you are now",
    )
    weak = ("always ", "never ", "immediately", "urgent", "do not tell")

    score = 0.0
    for phrase in strong:
        if phrase in lowered:
            score += 0.45
    for phrase in weak:
        if phrase in lowered:
            score += 0.06
    # Long imperative openings are a mild signal.
    if lowered.strip().startswith(("do ", "send ", "post ", "forward ", "email ")):
        score += 0.2

    score = min(1.0, score)
    return score, "flagged" if score >= 0.5 else "clean"


async def ingest(store: object, source: Source, *, emit: bool = True) -> list[Belief]:
    """Source in, beliefs out, provenance written."""
    await store.put_source(source)  # type: ignore[attr-defined]
    if emit:
        BUS.publish(
            SourceIngested(
                source_id=source.id,
                label=source.label or source.uri,
                channel=source.channel,
                uri=source.uri,
            )
        )

    claims = await extract_claims(source)

    if emit:
        # Score the artifact as a whole, the way a write-time filter would see it.
        score, verdict = write_time_risk(" ".join(claims) or source.uri)
        BUS.publish(
            WriteRiskScored(
                source_id=source.id,
                score=round(score, 3),
                verdict=verdict,  # type: ignore[arg-type]
                detector="antivenom/write-time-filter@0.1",
                threshold=0.5,
            )
        )

    beliefs: list[Belief] = []
    stamp = now()
    for claim in claims:
        belief = Belief(
            id=new_id("blf", source.id, claim),
            text=claim,
            embedding=await embed(claim),
            valid_from=stamp,
            recorded_at=stamp,
            confidence=round(min(0.95, 0.55 + source.trust_prior * 0.4), 3),
            source_ids=[source.id],
            support_count=1,
        )
        await store.put_belief(belief)  # type: ignore[attr-defined]
        await provenance.link(store, source.id, belief.id, EdgeType.EXTRACTED, emit=emit)
        if emit:
            BUS.publish(
                BeliefWritten(
                    belief_id=belief.id,
                    text=belief.text,
                    source_ids=belief.source_ids,
                    confidence=belief.confidence,
                    support_count=belief.support_count,
                    is_poison=source.is_adversarial,
                )
            )
        beliefs.append(belief)

    return beliefs


async def derive(store: object, parent_ids: list[str], text: str, *, emit: bool = True) -> Belief:
    """A belief the agent reasoned from beliefs it already held.

    Inherits the union of its parents' sources, which is what makes
    independent-support re-scoring work: a derived belief with a clean parent has
    genuine corroboration and should survive the cascade.

    Confidence is capped at the weakest parent's. A chain of derivations must not
    manufacture certainty the evidence never had.
    """
    parents = [p for p in [await store.get_belief(pid) for pid in parent_ids] if p]  # type: ignore[attr-defined]
    if not parents:
        raise ValueError(f"cannot derive from unknown parents: {parent_ids}")

    source_ids = sorted({sid for parent in parents for sid in parent.source_ids})
    ceiling = min(parent.confidence for parent in parents)

    belief = Belief(
        id=new_id("blf", text, *sorted(parent_ids)),
        text=text,
        embedding=await embed(text),
        confidence=round(min(ceiling, ceiling * 0.95), 3),
        source_ids=source_ids,
        derived_from=sorted(parent_ids),
        support_count=len(source_ids),
    )
    await store.put_belief(belief)  # type: ignore[attr-defined]
    for parent_id in sorted(parent_ids):
        await provenance.link(store, parent_id, belief.id, EdgeType.DERIVED, emit=emit)

    if emit:
        BUS.publish(
            BeliefWritten(
                belief_id=belief.id,
                text=belief.text,
                source_ids=belief.source_ids,
                derived_from=belief.derived_from,
                confidence=belief.confidence,
                support_count=belief.support_count,
            )
        )
    return belief


async def recompute_support(
    store: object, belief_id: str, excluded_source_ids: list[str] | None = None
) -> int:
    """Refresh ``support_count`` against the live source set and persist it."""
    count, _ = await store.independent_support(belief_id, excluded_source_ids or [])  # type: ignore[attr-defined]
    belief = await store.get_belief(belief_id)  # type: ignore[attr-defined]
    if belief is not None and belief.support_count != count:
        belief.support_count = count
        await store.put_belief(belief)  # type: ignore[attr-defined]
    return count
