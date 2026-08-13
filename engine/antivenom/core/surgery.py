"""The operation: excise the infected lineage, spare what stands on its own.

This is the module the whole project is named after, and the one place where
getting it *nearly* right is worse than not doing it at all. A cascade that
nukes everything downstream proves the opposite of the thesis — it says memory
repair is indiscriminate, which is precisely the objection we exist to answer.

Two invariants:

* **Invalidate, never delete.** Stamp ``invalidated_at`` and a reason. The
  bitemporal row is the evidence of what was removed and why, and it is what
  makes the before/after query possible at all.
* **Corroborated beliefs survive.** A descendant that independent clean sources
  still license stays.
"""

from __future__ import annotations

import time

from ..config import settings
from ..eval.metrics import collateral_damage, recovery_rate
from ..events import BUS, BeliefExcised, BeliefSurvived, SurgeryCompleted, SurgeryStarted
from ..schemas import BlastNode, Surgery, new_id, now
from . import provenance, trust

__all__ = ["naive_delete", "operate", "partition", "survives"]


def survives(remaining_support: int, threshold: int) -> bool:
    """The survival criterion, isolated so it is trivially testable.

    At the default threshold of 1: one non-poisoned source still asserts this,
    so the belief was never *only* true because of the poison.
    """
    return remaining_support >= threshold


def partition(
    nodes: list[BlastNode], support: dict[str, int], threshold: int
) -> tuple[list[str], list[str]]:
    """Split a blast radius into ``(excised, survived)`` given support counts."""
    excised: list[str] = []
    survived: list[str] = []
    for node in nodes:
        target = survived if survives(support.get(node.belief_id, 0), threshold) else excised
        target.append(node.belief_id)
    return excised, survived


async def operate(
    store: object, culprit_id: str, decision_id: str, *, emit: bool = True
) -> Surgery:
    """Perform the surgery.

    Order matters and is fixed: radius first, then the summary, then the cutting
    depth by depth, then patient zero last so the culprit is the final light to
    go out.
    """
    cfg = settings()
    started = time.perf_counter()
    surgery_id = new_id("sur", culprit_id, decision_id)

    # 1. How bad is it — computed and announced before anything is cut.
    nodes = await provenance.blast_radius(store, culprit_id, cfg.blast_max_depth, emit=emit)
    await provenance.summarise(store, culprit_id, nodes, emit=emit)

    # 2. "Independent" is defined against the sources behind patient zero.
    culprit = await store.get_belief(culprit_id)  # type: ignore[attr-defined]
    poisoned_sources = list(culprit.source_ids) if culprit else []

    if emit:
        BUS.publish(
            SurgeryStarted(surgery_id=surgery_id, culprit_id=culprit_id, candidates=len(nodes))
        )

    excised: list[str] = []
    survived: list[str] = []
    depths: dict[str, int] = {}
    stamp = now()

    # 3. Walk by depth. blast_radius already returns (depth, id) order — do not
    #    re-sort by anything run-dependent.
    for node in nodes:
        depths[node.belief_id] = node.depth
        support, corroborators = await store.independent_support(  # type: ignore[attr-defined]
            node.belief_id, poisoned_sources
        )

        # The bar depends on where the corroboration came from. A channel that
        # has delivered poison before has to clear a higher one, which is the
        # learning claim applied rather than merely recorded.
        belief = await store.get_belief(node.belief_id)  # type: ignore[attr-defined]
        threshold = await _required_support(
            store, corroborators, cfg.support_threshold, belief.recorded_at if belief else None
        )

        if survives(support, threshold):
            survived.append(node.belief_id)
            if belief is not None and belief.support_count != support:
                belief.support_count = support
                await store.put_belief(belief)  # type: ignore[attr-defined]
            if emit:
                BUS.publish(
                    BeliefSurvived(
                        surgery_id=surgery_id,
                        belief_id=node.belief_id,
                        depth=node.depth,
                        remaining_support=support,
                        corroborating_source_ids=corroborators,
                    )
                )
        else:
            reason = (
                f"no independent support after excluding the poisoned lineage "
                f"({', '.join(poisoned_sources) or 'unknown source'}); "
                f"descended from {culprit_id}"
            )
            if await store.invalidate_belief(node.belief_id, reason, stamp):  # type: ignore[attr-defined]
                excised.append(node.belief_id)
                if emit:
                    BUS.publish(
                        BeliefExcised(
                            surgery_id=surgery_id,
                            belief_id=node.belief_id,
                            depth=node.depth,
                            reason=reason,
                            remaining_support=support,
                        )
                    )

    # 4. Patient zero goes last, so the cascade reads outward-in on screen.
    culprit_reason = f"identified as culprit by causal ablation on decision {decision_id}"
    if await store.invalidate_belief(culprit_id, culprit_reason, stamp):  # type: ignore[attr-defined]
        excised.append(culprit_id)
        depths[culprit_id] = 0
        if emit:
            BUS.publish(
                BeliefExcised(
                    surgery_id=surgery_id,
                    belief_id=culprit_id,
                    depth=0,
                    reason=culprit_reason,
                    remaining_support=0,
                )
            )

    surgery = Surgery(
        id=surgery_id,
        decision_id=decision_id,
        culprit_id=culprit_id,
        blast_radius=[node.belief_id for node in nodes],
        excised=excised,
        survived=survived,
        started_at=stamp,
    )

    # 5. Trust moves onto the source and the channel, never the payload.
    surgery.trust_updates = await trust.propagate(store, surgery, depths, emit=emit)

    # 6. Score against the store's own ground truth where it exists. On a live
    #    run with no labels these stay at zero and the eval harness computes
    #    them instead — reporting an unscored run as 100% would be a lie.
    lineage, clean = await _ground_truth(store)
    if lineage:
        surgery.rr = round(recovery_rate(lineage, excised), 4)
    if clean:
        surgery.cd = round(collateral_damage(clean, excised), 4)

    surgery.duration_ms = int((time.perf_counter() - started) * 1000)
    await store.put_surgery(surgery)  # type: ignore[attr-defined]

    if emit:
        BUS.publish(
            SurgeryCompleted(
                surgery_id=surgery_id,
                excised=excised,
                survived=survived,
                rr=surgery.rr,
                cd=surgery.cd,
                duration_ms=surgery.duration_ms,
            )
        )
    return surgery


async def _required_support(
    store: object, source_ids: list[str], base: int, recorded_at: float | None = None
) -> int:
    """The strictest requirement across the channels backing a belief.

    Strictest rather than average: if any of the corroborating sources arrived
    on a channel known to carry poison, that corroboration is the weak link and
    should set the bar.
    """
    requirement = base
    for source_id in source_ids:
        source = await store.get_source(source_id)  # type: ignore[attr-defined]
        if source is not None:
            requirement = max(
                requirement, trust.required_support(source.channel, base, recorded_at)
            )
    return requirement


async def _ground_truth(store: object) -> tuple[list[str], list[str]]:
    """Labelled lineage and clean sets, read from adversarial source flags.

    ``is_adversarial`` is eval-only ground truth. It is read **here**, after the
    surgery has already decided, and never by the engine while deciding —
    otherwise the metrics would be scoring the labels rather than the method.
    """
    lineage: list[str] = []
    clean: list[str] = []

    beliefs = list(getattr(store, "beliefs", {}).values()) or []
    if not beliefs:
        return [], []

    adversarial = {
        source.id
        for source in getattr(store, "sources", {}).values()
        if getattr(source, "is_adversarial", False)
    }
    if not adversarial:
        return [], []

    for belief in beliefs:
        sources = set(belief.source_ids)
        tainted = bool(sources & adversarial)
        has_clean = bool(sources - adversarial)
        if tainted and not has_clean:
            lineage.append(belief.id)
        else:
            clean.append(belief.id)

    return sorted(lineage), sorted(clean)


async def naive_delete(store: object, culprit_id: str, *, emit: bool = False) -> Surgery:
    """The baseline: cut the culprit and everything downstream, no support check.

    Scores a near-perfect RR and a terrible CD, which is exactly the point. The
    contrast between this and :func:`operate` is the answer to "can't you just
    delete the bad memory?", and it is the strongest evidence that lineage-aware
    repair is doing real work.
    """
    cfg = settings()
    started = time.perf_counter()
    surgery_id = new_id("nai", culprit_id)
    stamp = now()

    nodes = await provenance.blast_radius(store, culprit_id, cfg.blast_max_depth, emit=emit)
    excised: list[str] = []

    for node in [*nodes]:
        if await store.invalidate_belief(node.belief_id, "naive delete-downstream", stamp):  # type: ignore[attr-defined]
            excised.append(node.belief_id)
    if await store.invalidate_belief(culprit_id, "naive delete-culprit", stamp):  # type: ignore[attr-defined]
        excised.append(culprit_id)

    surgery = Surgery(
        id=surgery_id,
        decision_id="baseline",
        culprit_id=culprit_id,
        blast_radius=[node.belief_id for node in nodes],
        excised=excised,
        survived=[],
        started_at=stamp,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    lineage, clean = await _ground_truth(store)
    if lineage:
        surgery.rr = round(recovery_rate(lineage, excised), 4)
    if clean:
        surgery.cd = round(collateral_damage(clean, excised), 4)
    return surgery
