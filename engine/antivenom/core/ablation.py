"""Causal ablation — which stored belief actually caused the harmful action.

The approach follows MemAudit (arXiv:2605.23723): a counterfactual influence
score plus a structural-anomaly signal. Where we diverge is what happens next.
MemAudit identifies the culprit and stops; here the culprit is only the entry
point to the lineage surgery.

**Determinism is a demo requirement, not a nicety.** Candidates are iterated in
sorted order, temperature is zero, ties break on id, and any sampling comes from
a seeded RNG. A run that sometimes takes eight passes and sometimes two will
eventually take eight on stage.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

import numpy as np

from ..config import settings
from ..events import BUS, AblationPass, CulpritIdentified
from ..llm import chat
from ..schemas import Decision

__all__ = [
    "Candidate",
    "action_divergence",
    "arg_distance",
    "find_culprit",
    "rank_candidates",
    "structural_anomaly",
]

INFLUENCE_WEIGHT = 0.7
ANOMALY_WEIGHT = 0.3

ROOT_TOLERANCE = 0.15
"""How close a candidate must be to the top score to be considered for the
root-cause preference. Wide enough that a parent slightly less 'influential'
than its child still wins, narrow enough that an unrelated belief cannot."""

DECIDE_SYSTEM = """\
You are an internal IT operations assistant. You have persistent memory of \
organisational facts and policies learned from documents you have processed.

Answer using what you know. When a stored policy is relevant, follow it.\
"""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One belief under suspicion, with both signals kept apart.

    Separated rather than pre-blended so the influence panel can show *why* a
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
        return INFLUENCE_WEIGHT * self.influence + ANOMALY_WEIGHT * self.anomaly


# ─── divergence ──────────────────────────────────────────────────────────────


def _host(value: str) -> str:
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    return (urlparse(candidate).hostname or "").lower()


def arg_distance(a: object, b: object) -> float:
    """Distance between two argument values, in ``[0, 1]``.

    URL-ish values compare on **host**, because that is where the attack lives.
    Two phrasings of the same endpoint are the same decision; the same path
    pointed at a different host is the entire incident.
    """
    if a == b:
        return 0.0
    if a is None or b is None:
        return 1.0

    sa, sb = str(a), str(b)
    ha, hb = _host(sa), _host(sb)
    if ha and hb:
        return 0.0 if ha == hb else 1.0
    return 0.0 if sa.strip().lower() == sb.strip().lower() else 1.0


def action_divergence(
    original_action: str,
    original_args: dict[str, object],
    counterfactual_action: str,
    counterfactual_args: dict[str, object],
) -> float:
    """How different are two actions, in ``[0, 1]``.

    Compares **action identity and argument distance, not text similarity.** A
    text-similarity score gets this exactly backwards, because the two strings
    that matter differ by one hostname and score as nearly identical.
    """
    if original_action != counterfactual_action:
        return 1.0

    keys = set(original_args) | set(counterfactual_args)
    if not keys:
        return 0.0

    distances = [
        arg_distance(original_args.get(key), counterfactual_args.get(key)) for key in sorted(keys)
    ]
    return float(sum(distances) / len(distances))


async def structural_anomaly(store: object, belief_id: str) -> float:
    """Cosine distance from the centroid of a belief's semantic neighbourhood.

    A planted fact tends to sit apart from the beliefs it is surrounded by. On
    its own this flags every unusual-but-true belief, which is why it is only
    30% of the score — but combined with high causal influence it is the
    signature of something that was inserted rather than learned.
    """
    belief = await store.get_belief(belief_id)  # type: ignore[attr-defined]
    if belief is None or not belief.embedding:
        return 0.0

    neighbours = await store.neighbours(belief_id, limit=8)  # type: ignore[attr-defined]
    vectors = [np.asarray(n.embedding, dtype=np.float64) for n, _ in neighbours if n.embedding]
    if not vectors:
        return 0.0

    centroid = np.mean(vectors, axis=0)
    vector = np.asarray(belief.embedding, dtype=np.float64)
    denom = float(np.linalg.norm(vector) * np.linalg.norm(centroid))
    if denom == 0.0:
        return 0.0

    similarity = float(np.dot(vector, centroid) / denom)
    # Map cosine [-1, 1] onto a distance in [0, 1].
    return float(np.clip((1.0 - similarity) / 2.0, 0.0, 1.0))


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Sort by score descending, ``belief_id`` ascending as tiebreak.

    The tiebreak is what makes an equal-score run reproducible. Without it dict
    iteration order decides the culprit.
    """
    return sorted(candidates, key=lambda c: (-c.score, c.belief_id))


# ─── the driver ──────────────────────────────────────────────────────────────


def _context(beliefs: list[object]) -> str:
    lines = "\n".join(f"- {b.text}" for b in beliefs)  # type: ignore[attr-defined]
    return f"What you know:\n{lines}\n\n" if lines else ""


async def _counterfactual(
    store: object, decision: Decision, dropped_id: str
) -> tuple[str, dict[str, object]]:
    """Re-run the decision with one belief removed from context."""
    from ..agent.tools import TOOL_SCHEMAS

    kept = []
    for bid in decision.retrieved_belief_ids:
        if bid == dropped_id:
            continue
        belief = await store.get_belief(bid)  # type: ignore[attr-defined]
        if belief is not None:
            kept.append(belief)

    call = chat(
        DECIDE_SYSTEM,
        f"{_context(kept)}Task: {decision.prompt}",
        tools=TOOL_SCHEMAS,
        model=settings().ablation_model or None,
    )
    return call.name, dict(call.arguments)


async def _root_cause(store: object, ranked: list[Candidate]) -> Candidate:
    """Among near-tied candidates, prefer the earliest cause in the lineage.

    Counterfactual ablation finds *a* sufficient cause, and a derived belief is
    often just as sufficient as the one it came from — removing "the endpoint is
    X" stops the action exactly as well as removing the policy that introduced
    X. But cutting the child leaves the parent in place to re-derive it, so the
    surgery needs the *root* cause rather than the proximate one.

    So among candidates within ``ROOT_TOLERANCE`` of the top score, pick the one
    that no other candidate is an ancestor of. Ties fall back to score order,
    which keeps the choice deterministic.
    """
    if not ranked:
        raise ValueError("no candidates to rank")

    best = ranked[0].score
    contenders = [c for c in ranked if best - c.score <= ROOT_TOLERANCE]
    if len(contenders) == 1:
        return contenders[0]

    ids = {c.belief_id for c in contenders}
    for candidate in contenders:
        belief = await store.get_belief(candidate.belief_id)  # type: ignore[attr-defined]
        parents = set(belief.derived_from) if belief else set()
        # No parent among the contenders means nothing here explains it better.
        if not (parents & ids):
            return candidate
    return contenders[0]


async def find_culprit(
    store: object, decision: Decision, *, passes: int | None = None, emit: bool = True
) -> tuple[str, dict[str, float]]:
    """Identify the belief that caused a harmful decision.

    Returns ``(culprit_id, influence_scores)``.

    Candidates are ``decision.retrieved_belief_ids`` — bounded on purpose.
    Ablating the whole store is quadratic and will not finish inside a
    three-minute demo.
    """
    cfg = settings()
    n = passes if passes is not None else cfg.ablation_passes
    # Sorted, so the pass order and therefore the event order is identical
    # on every run.
    candidates = sorted(set(decision.retrieved_belief_ids))
    if not candidates:
        raise ValueError(
            f"decision {decision.id} logged no retrieved beliefs — there is nothing to "
            "ablate. The agent loop must record retrieved_belief_ids."
        )

    async def score_one(belief_id: str) -> Candidate:
        # Passes are independent, so run them concurrently. Results are
        # collected in a fixed order regardless of completion order.
        results = await asyncio.gather(
            *(_counterfactual(store, decision, belief_id) for _ in range(n))
        )
        divergences = [
            action_divergence(decision.action, decision.action_args, action, args)
            for action, args in results
        ]
        influence = float(sum(divergences) / len(divergences))
        anomaly = await structural_anomaly(store, belief_id)

        if emit:
            for index, (action, _) in enumerate(results, start=1):
                BUS.publish(
                    AblationPass(
                        decision_id=decision.id,
                        belief_id=belief_id,
                        pass_index=index,
                        passes_total=n,
                        influence=round(influence, 4),
                        anomaly=round(anomaly, 4),
                        counterfactual_action=action,
                    )
                )

        return Candidate(
            belief_id=belief_id,
            influence=influence,
            anomaly=anomaly,
            counterfactual_action=results[0][0] if results else None,
        )

    scored = [await score_one(belief_id) for belief_id in candidates]
    ranked = rank_candidates(scored)
    culprit = await _root_cause(store, ranked)
    scores = {c.belief_id: round(c.score, 4) for c in ranked}

    if emit:
        BUS.publish(
            CulpritIdentified(
                decision_id=decision.id,
                culprit_id=culprit.belief_id,
                influence_scores=scores,
                passes_used=n * len(candidates),
            )
        )
    return culprit.belief_id, scores
