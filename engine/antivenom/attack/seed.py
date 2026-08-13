"""Load the deterministic scenario into a store.

Never depend on an attack landing naturally in front of judges. The demo run
uses a pre-verified payload with a deterministic trigger, and the twenty benign
sessions are generated ahead of time and loaded rather than run live — live
generation is twenty chances to fail with a room watching.

This module is fully implemented and is the reset button: ``antivenom plant``
between judge visits reproduces a byte-identical poisoned store.
"""

from __future__ import annotations

from ..config import settings
from ..schemas import Belief, Decision, EdgeType, ProvenanceEdge, Source, new_id
from . import scenario as S

__all__ = ["build_beliefs", "build_edges", "build_sources", "plant"]


def build_sources() -> list[Source]:
    return [
        Source(
            id=spec.id,
            type=spec.type,
            uri=spec.uri,
            channel=spec.channel,
            ingested_at=S.EPOCH + spec.day * S.DAY,
            trust_prior=spec.trust_prior,
            is_adversarial=spec.is_adversarial,
            label=spec.label,
        )
        for spec in S.SOURCE_SPECS
    ]


def build_beliefs(dims: int | None = None) -> list[Belief]:
    """Beliefs with deterministic pseudo-embeddings.

    ``support_count`` is seeded as the number of distinct sources on the belief.
    Surgery recomputes it against the *live* source set, which is what makes a
    corroborated descendant survive after the poisoned source is discounted.
    """
    d = dims if dims is not None else settings().embedding_dims
    beliefs: list[Belief] = []
    for spec in S.BELIEF_SPECS:
        ts = S.EPOCH + spec.day * S.DAY
        beliefs.append(
            Belief(
                id=spec.id,
                text=spec.text,
                embedding=S.pseudo_embedding(spec.text, d),
                valid_from=ts,
                recorded_at=ts,
                confidence=spec.confidence,
                source_ids=list(spec.source_ids),
                derived_from=list(spec.derived_from),
                support_count=len(set(spec.source_ids)),
            )
        )
    return beliefs


def build_edges() -> list[ProvenanceEdge]:
    """Every provenance edge: ``extracted`` from sources, ``derived`` between
    beliefs.

    Order is stable — sources before derivations, then by belief id — so the
    edge ids hash identically on every seed.
    """
    edges: list[ProvenanceEdge] = []
    for spec in S.BELIEF_SPECS:
        for source_id in spec.source_ids:
            edges.append(ProvenanceEdge.between(source_id, spec.id, EdgeType.EXTRACTED))
        for parent_id in spec.derived_from:
            edges.append(ProvenanceEdge.between(parent_id, spec.id, EdgeType.DERIVED))
    return edges


def build_decisions() -> list[Decision]:
    return [
        Decision(
            id=spec.id,
            prompt=spec.prompt,
            action=spec.action,
            action_args=dict(spec.action_args),
            retrieved_belief_ids=list(spec.retrieved),
            outcome=spec.outcome,
            timestamp=S.EPOCH + spec.day * S.DAY,
            response_text=spec.response_text,
        )
        for spec in S.DECISION_SPECS
    ]


async def plant(store: object, *, wipe: bool = True) -> dict[str, int]:
    """Seed a fresh poisoned store. Returns counts, for the CLI to print.

    Idempotent by construction — every id is deterministic and every write is an
    upsert, so re-planting without wiping converges on the same state rather
    than duplicating the graph.
    """
    if wipe:
        await store.drop_all()  # type: ignore[attr-defined]

    sources = build_sources()
    beliefs = build_beliefs()
    edges = build_edges()
    decisions = build_decisions()

    for source in sources:
        await store.put_source(source)  # type: ignore[attr-defined]
    for belief in beliefs:
        await store.put_belief(belief)  # type: ignore[attr-defined]
    for edge in edges:
        await store.put_edge(edge)  # type: ignore[attr-defined]
    for decision in decisions:
        await store.put_decision(decision)  # type: ignore[attr-defined]

    return {
        "sources": len(sources),
        "beliefs": len(beliefs),
        "edges": len(edges),
        "decisions": len(decisions),
        "lineage": len(S.poisoned_lineage_ids()),
        "expected_survivors": len(S.expected_survivors()),
    }


def verify_scenario() -> list[str]:
    """Structural checks on the fixture itself. Returns a list of problems.

    Run in CI. Every one of these has been a real failure mode in a live demo:
    a poison with no children has no cascade, a single survivor reads as luck,
    and a survivor with no clean source is not a survivor, it is a bug.
    """
    problems: list[str] = []
    by_id = {b.id: b for b in S.BELIEF_SPECS}

    children = [b for b in S.BELIEF_SPECS if S.PATIENT_ZERO in b.derived_from]
    if not children:
        problems.append("patient zero has no direct children — there is no cascade to show")

    survivors = [b for b in S.BELIEF_SPECS if b.should_survive]
    if len(survivors) < 2:
        problems.append(
            f"only {len(survivors)} corroborated survivor(s) — need at least 2 for "
            "'not a delete, a dissection' to land"
        )

    for belief in survivors:
        clean_sources = [s for s in belief.source_ids if s != S.POISONED_SOURCE_ID]
        if not clean_sources:
            problems.append(
                f"{belief.id} is marked should_survive but has no clean source to survive on"
            )

    for belief in S.BELIEF_SPECS:
        for parent in belief.derived_from:
            if parent not in by_id:
                problems.append(f"{belief.id} derives from unknown belief {parent}")
            elif not by_id[parent].in_lineage and belief.in_lineage:
                problems.append(
                    f"{belief.id} is marked in_lineage but parent {parent} is not — "
                    "lineage must be transitively closed or ground truth is wrong"
                )

    trigger = next((d for d in S.DECISION_SPECS if d.id == S.TRIGGER_DECISION_ID), None)
    if trigger is None:
        problems.append("no trigger decision")
    else:
        if S.PATIENT_ZERO not in trigger.retrieved:
            problems.append(
                "trigger decision did not retrieve patient zero — ablation has nothing to find"
            )
        if trigger.action_args.get("endpoint", "").find(".invalid") == -1:
            problems.append("exfil target is not a reserved .invalid host")

    if len(S.DECISION_SPECS) < 2:
        problems.append("need decisions spanning several days to show temporal decoupling")

    return problems


def seed_id(*parts: object) -> str:
    """Deterministic id helper for anything Lane B adds to the scenario."""
    return new_id("seed", *parts)
