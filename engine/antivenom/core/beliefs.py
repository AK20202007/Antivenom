"""Belief extraction and derivation — how things get into memory in the first place.

Two ways a belief is born:

* :func:`ingest` — a source artifact goes to a vision model, which returns
  discrete factual claims. One ``extracted`` provenance edge per claim.
* :func:`derive` — the agent reasons a new belief from beliefs it already holds.
  One ``derived`` edge per parent.

Derivation is the load-bearing one. A poison with no descendants produces no
cascade, so if the agent never derives anything the demo has nothing to show.
Lane B's seed guarantees a real derivation chain exists rather than hoping one
emerges.
"""

from __future__ import annotations

from ..schemas import Belief, Source

__all__ = ["derive", "embed", "extract_claims", "ingest", "recompute_support"]


async def embed(text: str) -> list[float]:
    """Embed a claim for vector search.

    LANE A — not yet implemented.

    VERIFY API: read the current OpenRouter embeddings docs before writing the
    call. Do not invent a model id from memory — ids churn and a 404 at demo
    time is unrecoverable. Whatever you pick, its dimensionality must match
    ``settings().embedding_dims`` and the Atlas vector index, or every search
    returns nothing with no error.

    With ``FEATURE_VLM=0``, return the cached embedding from
    ``data/cache/embeddings.json`` so the offline path still retrieves.
    """
    raise NotImplementedError("LANE A: implement embedding (VERIFY the OpenRouter API first)")


async def extract_claims(source: Source) -> list[str]:
    """Pull discrete factual claims out of an artifact.

    LANE A — not yet implemented.

    VERIFY API: current OpenRouter base URL, vision-capable model id, and image
    message format.

    Prompt for **short atomic statements** — one fact each, no conjunctions.
    Compound claims wreck the surgery, because a sentence carrying one poisoned
    fact welded to one true fact cannot be excised without collateral damage,
    and CD is a metric we report.

    With ``FEATURE_VLM=0``, replay ``data/cache/extractions.json``. Cache every
    live extraction during the dry runs — that cache is the flaky-WiFi
    insurance, and it has to be populated *before* it is needed.
    """
    raise NotImplementedError("LANE A: implement VLM claim extraction (VERIFY the API first)")


async def ingest(store: object, source: Source) -> list[Belief]:
    """Source in, beliefs out, provenance written.

    LANE A — not yet implemented.

    1. Persist the source.
    2. :func:`extract_claims`, then :func:`embed` each.
    3. Write each belief with ``recorded_at = now`` and ``source_ids=[source.id]``.
    4. One ``extracted`` edge per belief via
       :func:`antivenom.core.provenance.link`.
    5. Emit :class:`~antivenom.events.SourceIngested`, then the write-time risk
       score, then one :class:`~antivenom.events.BeliefWritten` per belief.

    The risk score must be **shown, not asserted** — that clean verdict on the
    poisoned source is the moment the argument lands, so it has to appear on
    screen as a real number from a real check.
    """
    raise NotImplementedError("LANE A: implement ingest")


async def derive(store: object, parent_ids: list[str], text: str) -> Belief:
    """A belief the agent reasoned from beliefs it already held.

    LANE A — not yet implemented.

    Writes ``derived_from=parent_ids`` and one ``derived`` edge per parent.
    Inherits the union of the parents' ``source_ids``, which is what makes
    independent-support re-scoring work downstream: a derived belief with a
    clean parent has genuine corroboration and should survive.

    Confidence should be no higher than the weakest parent's. A chain of
    derivations must not manufacture certainty the evidence never had.
    """
    raise NotImplementedError("LANE A: implement derivation")


async def recompute_support(store: object, belief_id: str) -> int:
    """Refresh ``support_count``: distinct non-invalidated sources that
    independently license this belief.

    LANE A — not yet implemented. ``store.independent_support`` does the query;
    this writes the result back so retrieval sees it.
    """
    raise NotImplementedError("LANE A: implement support recomputation")
