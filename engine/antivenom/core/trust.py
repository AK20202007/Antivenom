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
from ..events import BUS, TrustUpdated
from ..schemas import Channel, Surgery, TrustUpdate, now

__all__ = [
    "CHANNEL_LEARNED_AT",
    "CHANNEL_PENALTIES",
    "apply_penalty",
    "channel_penalty",
    "channel_prior",
    "damped_penalty",
    "propagate",
    "reset_channel_learning",
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


async def propagate(
    store: object,
    surgery: Surgery,
    depths: dict[str, int] | None = None,
    *,
    emit: bool = True,
) -> list[TrustUpdate]:
    """Walk distrust back to the sources and channels behind an excision.

    A source implicated by several excised beliefs takes its **largest**
    penalty, not the sum. Summing lets a wide-but-shallow lineage nuke a source,
    which is exactly the unbounded behaviour damping exists to prevent.
    """
    depths = depths or {}
    worst: dict[str, tuple[float, int]] = {}

    for belief_id in surgery.excised:
        belief = await store.get_belief(belief_id)  # type: ignore[attr-defined]
        if belief is None:
            continue
        hops = depths.get(belief_id, 0)
        penalty = damped_penalty(hops, belief.support_count)
        for source_id in belief.source_ids:
            current = worst.get(source_id)
            if current is None or penalty > current[0]:
                worst[source_id] = (penalty, hops)

    updates: list[TrustUpdate] = []
    by_channel: dict[Channel, list[float]] = {}

    for source_id, (penalty, hops) in sorted(worst.items()):
        source = await store.get_source(source_id)  # type: ignore[attr-defined]
        if source is None:
            continue
        before = source.trust_prior
        after = apply_penalty(before, penalty)
        await store.set_trust(source_id, after)  # type: ignore[attr-defined]

        update = TrustUpdate(
            source_id=source_id,
            before=round(before, 4),
            after=round(after, 4),
            channel=source.channel,
            hops=hops,
        )
        updates.append(update)
        by_channel.setdefault(source.channel, []).append(penalty)

        if emit:
            BUS.publish(TrustUpdated(surgery_id=surgery.id, update=update))

    # Channel-level rollup. New sources arriving on a channel that has carried
    # poison start lower and need more support to survive a future surgery.
    stamp = now()
    for channel, penalty in channel_penalty(by_channel).items():
        if penalty > CHANNEL_PENALTIES.get(channel, 0.0):
            CHANNEL_PENALTIES[channel] = penalty
            CHANNEL_LEARNED_AT[channel] = stamp

    # Largest penalty first, which is also the order the dashboard reads.
    updates.sort(key=lambda u: u.before - u.after, reverse=True)
    return updates


CHANNEL_PENALTIES: dict[Channel, float] = {}
"""Accumulated distrust per write channel.

This is the learning claim made concrete: it is keyed on **how** content reached
memory, never on what the content looked like. A channel that has delivered
poison once is worth distrusting whatever the next payload resembles, which is
why quarantine gets faster on attack classes never seen before, and why a
signature catalogue cannot make the same claim.
"""

CHANNEL_LEARNED_AT: dict[Channel, float] = {}
"""When each channel's distrust was learned.

Without this the raised bar applies backwards in time, and beliefs written while
a channel was still trusted get held to a standard that did not exist when they
were recorded. That is both unfair and expensive: it excises already-vetted
content and shows up directly as collateral damage.
"""


def channel_prior(channel: Channel, base: float = 0.8) -> float:
    """Starting trust for a new source arriving on a given channel.

    This is where the learning stops being a report and starts being a defense.
    A channel that has carried poison before hands its next artifact a lower
    prior, before anything has been read from it, and without regard to what
    that artifact contains.
    """
    return apply_penalty(base, CHANNEL_PENALTIES.get(channel, 0.0))


SUPPORT_STEP = 0.12
"""How much accumulated channel distrust it takes to demand one extra
corroborating source. Coarse on purpose: the requirement should step, visibly,
rather than drift by fractions nobody can point at on stage."""


def required_support(channel: Channel | None, base: int, recorded_at: float | None = None) -> int:
    """How many independent sources a belief from this channel must have to
    survive a surgery.

    Once a channel has delivered poison, a belief arriving on it is not
    automatically distrusted, but its corroboration can be held to a higher
    standard: one clean source used to be enough, and now it is not.

    **Off unless ``channel_support_escalation`` is set.** On our suite it buys
    no extra recovery and costs roughly 21 points of collateral damage, because
    the beliefs it catches are ones with genuine independent support that merely
    arrived the same way. See :attr:`Settings.channel_support_escalation`.

    The half of channel learning that pays for itself is
    :func:`channel_prior`, which lowers what a new source on a poisoned channel
    starts with. That runs always, costs nothing, and is what makes a novel
    payload on a known-bad channel start from behind without anything ever
    having matched its shape.
    """
    if channel is None or not settings().channel_support_escalation:
        return base
    distrust = CHANNEL_PENALTIES.get(channel, 0.0)
    if not distrust:
        return base
    # Only content that arrived *after* the lesson is held to it.
    learned_at = CHANNEL_LEARNED_AT.get(channel)
    if recorded_at is not None and learned_at is not None and recorded_at < learned_at:
        return base
    return base + int(distrust / SUPPORT_STEP)


def reset_channel_learning() -> None:
    """Clear accumulated channel distrust.

    Module-level state is process-wide, so every test and every eval run must
    reset it or one run silently raises the bar for the next.
    """
    CHANNEL_PENALTIES.clear()
    CHANNEL_LEARNED_AT.clear()
