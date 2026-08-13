"""The operation: excise the infected lineage, spare what stands on its own.

This is the module the whole project is named after, and the one place where
getting it *nearly* right is worse than not doing it at all. A cascade that
nukes everything downstream proves the opposite of our thesis — it says memory
repair is indiscriminate, which is precisely the objection we exist to answer.

Two invariants:

* **Invalidate, never delete.** Stamp ``invalidated_at`` and a reason. The
  bitemporal row is the evidence of what was removed and why, and it is what
  makes the before/after query possible at all.
* **Corroborated beliefs survive.** A descendant that independent clean sources
  still license stays. At least two survivors is a demo requirement, because
  "not a delete, a dissection" needs something on screen to point at.
"""

from __future__ import annotations

from ..schemas import BlastNode

__all__ = ["operate", "survives"]


def survives(remaining_support: int, threshold: int) -> bool:
    """The survival criterion, isolated so it is trivially testable.

    A belief survives when independent clean support meets the threshold. At the
    default threshold of 1 that means: one non-poisoned source still asserts
    this, so the belief was never *only* true because of the poison.
    """
    return remaining_support >= threshold


async def operate(store: object, culprit_id: str, decision_id: str) -> object:
    """Perform the surgery. Returns a :class:`~antivenom.schemas.Surgery`.

    LANE A — not yet implemented.

    Algorithm:

    1. Compute the blast radius via :func:`antivenom.core.provenance.blast_radius`
       and emit the summary **first**.
    2. Collect the poisoned source set: the sources of patient zero, which is
       what "independent" is defined against.
    3. Walk descendants in depth order. For each, ``store.independent_support``
       excluding the poisoned sources, then :func:`survives`.
    4. Survivor: emit :class:`~antivenom.events.BeliefSurvived` with its
       corroborating source ids, and refresh its ``support_count``.
       Casualty: ``store.invalidate_belief`` with a reason naming the culprit,
       then emit :class:`~antivenom.events.BeliefExcised`.
    5. Invalidate patient zero itself last, so the cascade reads outward-in on
       screen and the culprit is the final light to go out.
    6. :func:`antivenom.core.trust.propagate`, then assemble and persist the
       Surgery record.

    **One event per belief.** Batching the excisions into a single event
    collapses the best thirty seconds of the demo into one frame.

    Ordering must be deterministic: iterate ``sorted(nodes, key=(depth, id))``.
    The blast radius already returns that order — do not re-sort it by anything
    run-dependent.
    """
    raise NotImplementedError(
        "LANE A: implement the surgery. survives() is done; this is the walk, "
        "the per-node events, and the Surgery record."
    )


async def naive_delete(store: object, culprit_id: str) -> object:
    """The baseline we compare against, for the ablation study.

    Invalidates the culprit and everything downstream with no support check.
    Expected to score a near-perfect RR and a terrible CD, which is the point:
    the contrast between this and :func:`operate` is the strongest evidence that
    lineage-aware repair is doing real work.

    LANE B owns wiring this into the eval harness.
    """
    raise NotImplementedError("LANE B: implement the naive-delete baseline for the ablation study")


def partition(
    nodes: list[BlastNode], support: dict[str, int], threshold: int
) -> tuple[list[str], list[str]]:
    """Split a blast radius into ``(excised, survived)`` given support counts.

    Pure, so the survival logic can be tested exhaustively without a store.
    """
    excised: list[str] = []
    survived: list[str] = []
    for node in nodes:
        target = survived if survives(support.get(node.belief_id, 0), threshold) else excised
        target.append(node.belief_id)
    return excised, survived
