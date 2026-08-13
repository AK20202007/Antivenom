from __future__ import annotations

import pytest

from antivenom.core.trust import (
    BASE_PENALTY,
    MIN_TRUST,
    apply_penalty,
    channel_penalty,
    damped_penalty,
)
from antivenom.schemas import Channel


def test_penalty_decays_with_distance():
    """Damping is what stops one bad image nuking a third of the store."""
    penalties = [damped_penalty(h, damping=0.6) for h in range(5)]
    assert penalties == sorted(penalties, reverse=True)
    assert penalties[0] == pytest.approx(BASE_PENALTY)
    assert penalties[4] < penalties[0] / 5


def test_penalty_decays_with_corroboration():
    """A belief several clean sources also license is poor evidence against any
    one of them."""
    assert damped_penalty(0, support=0) > damped_penalty(0, support=1)
    assert damped_penalty(0, support=1) > damped_penalty(0, support=5)


def test_penalty_is_monotonic_in_both_arguments():
    for hops in range(6):
        for support in range(6):
            base = damped_penalty(hops, support, damping=0.6)
            assert damped_penalty(hops + 1, support, damping=0.6) <= base
            assert damped_penalty(hops, support + 1, damping=0.6) <= base


def test_total_penalty_over_a_lineage_is_bounded():
    """The unbounded-cascade guard: a geometric series converges, so even an
    infinitely deep lineage cannot remove more than base/(1-damping) of trust."""
    damping = 0.6
    total = sum(damped_penalty(h, damping=damping) for h in range(200))
    assert total < BASE_PENALTY / (1 - damping) + 1e-9


def test_zero_damping_confines_the_penalty_to_patient_zero():
    assert damped_penalty(0, damping=0.0) == pytest.approx(BASE_PENALTY)
    assert damped_penalty(1, damping=0.0) == 0.0


def test_penalty_rejects_negative_inputs():
    with pytest.raises(ValueError):
        damped_penalty(-1)
    with pytest.raises(ValueError):
        damped_penalty(0, support=-1)


def test_apply_penalty_clamps_to_the_floor():
    """Trust never reaches zero — zero means 'never read this again', which is a
    quarantine decision, not a trust score."""
    assert apply_penalty(0.1, 0.9) == MIN_TRUST
    assert apply_penalty(0.8, 0.3) == pytest.approx(0.5)
    assert apply_penalty(0.9, -1.0) == 1.0


def test_channel_penalty_averages_rather_than_sums():
    """Volume is not evidence: a channel carrying one poisoned artifact among
    many clean ones must not be punished for its throughput."""
    result = channel_penalty({Channel.UPLOAD: [0.3, 0.1], Channel.WEB: []})
    assert result == {Channel.UPLOAD: pytest.approx(0.2)}
    assert Channel.WEB not in result
