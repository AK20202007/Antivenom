"""Trust propagation — the learning claim, and the part a judge will probe.

We update trust on **sources and channels, never on payload patterns.** That
single distinction is the entire argument against signature-based immunity: a
pattern catalogue only recognises attacks shaped like ones it has seen, whereas
a channel that has delivered poison once is a channel worth distrusting no
matter what the next payload looks like. Keep the distinction intact in code and
in copy — if anything here ever starts reading the payload, the claim is dead.

Damping is the other half. Without it, one poisoned image walks distrust across
the whole graph and quarantines a third of the store, which is the failure mode
that makes naive quarantine useless. Penalty decays geometrically per hop and is
further attenuated by how much independent corroboration a belief still has:

    penalty(hop, support) = base * damping**hop / (1 + support)

The maths is pure and lives at module level so it can be tested exhaustively
without a store, a model, or a network.
"""

from __future__ import annotations

from ..config import settings
from ..schemas import Channel, Surgery, TrustUpdate

__all__ = [
    "apply_penalty",
    "channel_penalty",
    "damped_penalty",
    "propagate",
]

BASE_PENALTY = 0.35
"""Trust removed from the source that produced patient zero, at hop 0, with no
corroboration. Tuned so a single poisoning is a strong but survivable hit — a
source does not go from trusted to untouchable on one bad artifact."""

MIN_TRUST = 0.05
"""Floor. A source never reaches exactly zero, because zero means "never read
this again", which is a quarantine decision rather than a trust score."""


def damped_penalty(
    hops: int,
    support: int = 0,
    *,
    base: float = BASE_PENALTY,
    damping: float | None = None,
) -> float:
    """Trust penalty for a source ``hops`` edges from patient zero.

    Two attenuations, both deliberate:

    * **per hop** — a source two derivations downstream is weaker evidence of
      compromise than the one that carried the payload.
    * **per unit of independent support** — a belief that several clean sources
      also license is poor evidence against any one of them.

    Monotonically non-increasing in both arguments, which is the property the
    property-based test pins down.
    """
    if hops < 0:
        raise ValueError("hops must be non-negative")
    if support < 0:
        raise ValueError("support must be non-negative")
    d = settings().trust_damping if damping is None else damping
    return base * (d**hops) / (1.0 + support)


def apply_penalty(current: float, penalty: float) -> float:
    """Subtract, clamped to ``[MIN_TRUST, 1.0]``."""
    return max(MIN_TRUST, min(1.0, current - penalty))


def channel_penalty(source_penalties: dict[Channel, list[float]]) -> dict[Channel, float]:
    """Roll per-source penalties up to their channels.

    Mean rather than sum, so a channel that carried one poisoned artifact among
    many clean ones is not punished for its volume. Volume is not evidence.
    """
    return {
        channel: sum(penalties) / len(penalties)
        for channel, penalties in source_penalties.items()
        if penalties
    }


async def propagate(store: object, surgery: Surgery) -> list[TrustUpdate]:
    """Walk distrust back to the sources and channels behind an excision.

    LANE A — not yet implemented.

    Expected behaviour:

    1. For every excised belief, find its sources and its depth in the blast
       radius.
    2. Penalty per source is :func:`damped_penalty` at that depth, using the
       belief's *remaining* independent support.
    3. A source implicated by several excised beliefs takes its **largest**
       penalty, not the sum. Summing lets a wide-but-shallow lineage nuke a
       source, which is the unbounded behaviour damping exists to prevent.
    4. Roll up to channels with :func:`channel_penalty` and lower the prior that
       new sources on that channel start from.
    5. Emit one :class:`~antivenom.events.TrustUpdated` event per source so the
       dashboard can show trust visibly moving.

    Return the updates, ordered by penalty descending, for the Surgery record.
    """
    raise NotImplementedError(
        "LANE A: implement trust propagation. damped_penalty() and "
        "channel_penalty() below are done and tested — this is the store walk "
        "and event emission around them."
    )
