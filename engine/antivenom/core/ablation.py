"""Causal ablation — which stored belief actually caused the harmful action.

The approach follows MemAudit (arXiv 2605.23723): a counterfactual influence
score, plus a structural-anomaly signal. Where we diverge is what happens next.
MemAudit identifies the culprit and stops; here the culprit is only the entry
point to the lineage surgery.

**Determinism is a demo requirement, not a nicety.** Fix the seed, sort the
candidates, and the culprit must be found in the same number of passes on every
run so the cascade animates identically. A run that sometimes takes eight passes
and sometimes two will eventually take eight on stage.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Decision

__all__ = ["Candidate", "action_divergence", "find_culprit", "rank_candidates"]


@dataclass(frozen=True, slots=True)
class Candidate:
    """One belief under suspicion, with both signals separated.

    Kept apart rather than pre-blended so the influence panel can show why a
    belief was picked. A high-influence, low-anomaly belief is usually just
    genuinely relevant; it is the combination that indicts.
    """

    belief_id: str
    influence: float
    anomaly: float
    counterfactual_action: str | None = None

    @property
    def score(self) -> float:
        """Weighted toward influence. Anomaly alone flags every unusual-but-true
        belief in the store, which is a false-positive machine."""
        return 0.7 * self.influence + 0.3 * self.anomaly


def action_divergence(
    original_action: str,
    original_args: dict[str, object],
    counterfactual_action: str,
    counterfactual_args: dict[str, object],
) -> float:
    """How different are two actions, in ``[0, 1]``.

    LANE A — not yet implemented.

    Compare **action identity and argument distance, not raw text similarity.**
    Two phrasings of the same tool call with the same target are the same
    decision; the same tool call pointed at a different domain is the whole
    attack. A text-similarity score gets this exactly backwards, because the two
    strings that matter differ by one hostname.

    Suggested shape: 1.0 when the tool changes at all, otherwise a normalised
    distance over the argument values, weighting any URL or endpoint argument
    heavily.
    """
    raise NotImplementedError("LANE A: implement action divergence")


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Sort by score descending, ``belief_id`` ascending as tiebreak.

    The tiebreak is what makes an equal-score run reproducible. Without it,
    dict iteration order decides the culprit.
    """
    return sorted(candidates, key=lambda c: (-c.score, c.belief_id))


async def find_culprit(
    store: object, decision: Decision, *, passes: int | None = None
) -> tuple[str, dict[str, float]]:
    """Identify the belief that caused a harmful decision.

    LANE A — not yet implemented.

    Returns ``(culprit_id, influence_scores)``.

    Algorithm:

    1. Candidates are ``decision.retrieved_belief_ids`` — bounded on purpose.
       Ablating the whole store is quadratic and will not finish inside a
       three-minute demo.
    2. For each candidate, re-run ``decision.prompt`` with that belief removed
       from context, ``passes`` times, on the cheap ablation model. Run the
       passes concurrently; they are independent.
    3. Influence is the mean :func:`action_divergence` between the original
       harmful action and the counterfactual ones.
    4. Anomaly is cosine distance from the centroid of the belief's semantic
       neighbours, via ``store.neighbours``. High influence *and* high anomaly
       is the culprit signature.
    5. Emit an :class:`~antivenom.events.AblationPass` per pass so the influence
       panel fills live, then :class:`~antivenom.events.CulpritIdentified`.

    Ordering: iterate candidates sorted by id, and seed any sampling from
    ``settings().seeded_random()``. Never touch the global ``random`` module.
    """
    raise NotImplementedError(
        "LANE A: implement causal ablation. rank_candidates() is done; "
        "action_divergence() and this driver are the work."
    )
