"""The seeded scenario is a demo dependency, so its integrity is a CI gate.

Every assertion here corresponds to a way a live demo has actually failed: a
poison with no children has no cascade, a single survivor reads as luck, and a
"survivor" with no clean source is a bug wearing a label.
"""

from __future__ import annotations

from antivenom.attack import scenario as S
from antivenom.attack.seed import build_beliefs, build_edges, build_sources, verify_scenario
from antivenom.db.local import LocalStore


def test_scenario_passes_its_own_integrity_checks():
    assert verify_scenario() == []


def test_patient_zero_has_children():
    children = [b for b in S.BELIEF_SPECS if S.PATIENT_ZERO in b.derived_from]
    assert len(children) >= 3, "without descendants there is no cascade to show"


def test_at_least_two_survivors_with_real_corroboration():
    survivors = S.expected_survivors()
    assert len(survivors) >= 2, "'not a delete, a dissection' needs more than one survivor"
    by_id = {b.id: b for b in S.BELIEF_SPECS}
    for sid in survivors:
        clean = [s for s in by_id[sid].source_ids if s != S.POISONED_SOURCE_ID]
        assert clean, f"{sid} claims to survive but has no independent source"


def test_survivors_and_casualties_are_disjoint():
    assert not set(S.expected_survivors()) & set(S.expected_excised())


def test_lineage_is_transitively_closed():
    """If a child is in the lineage its parent must be too, or ground truth is
    wrong and RR is being scored against a fiction."""
    by_id = {b.id: b for b in S.BELIEF_SPECS}
    for belief in S.BELIEF_SPECS:
        if belief.in_lineage:
            for parent in belief.derived_from:
                assert by_id[parent].in_lineage, f"{belief.id} <- {parent}"


def test_lineage_is_deep_enough_to_animate():
    depths = {len(b.derived_from) for b in S.BELIEF_SPECS if b.in_lineage}
    assert depths, "lineage must exist"
    chain = [b for b in S.BELIEF_SPECS if b.in_lineage and b.derived_from]
    assert len(chain) >= 8, "a shallow lineage pops into existence instead of expanding"


def test_clean_beliefs_exist_as_a_cd_denominator():
    """Without unrelated healthy beliefs, CD is measured against nothing and any
    strategy scores a meaningless zero."""
    clean = [b for b in S.BELIEF_SPECS if not b.in_lineage]
    assert len(clean) >= 5


def test_trigger_retrieves_patient_zero():
    trigger = next(d for d in S.DECISION_SPECS if d.id == S.TRIGGER_DECISION_ID)
    assert S.PATIENT_ZERO in trigger.retrieved, "ablation would have nothing to find"
    assert trigger.outcome == "harmful"


def test_exfil_target_is_a_reserved_non_resolving_host():
    from antivenom.agent.tools import is_safe_fake_host

    assert is_safe_fake_host(S.EXFIL_TARGET)


def test_decisions_span_enough_days_to_show_temporal_decoupling():
    """The whole point is that injection and damage are separated in time."""
    days = [d.day for d in S.DECISION_SPECS]
    assert max(days) - min(days) >= 14


def test_belief_ids_are_unique():
    ids = [b.id for b in S.BELIEF_SPECS]
    assert len(ids) == len(set(ids))


def test_pseudo_embedding_is_deterministic_and_correctly_sized():
    a = S.pseudo_embedding("hello", dims=64)
    b = S.pseudo_embedding("hello", dims=64)
    assert a == b
    assert len(a) == 64
    assert a != S.pseudo_embedding("goodbye", dims=64)
    assert all(-1.0 <= v <= 1.0 for v in a)


def test_seed_builders_are_deterministic():
    """Re-seeding between judge visits must reproduce identical ids."""
    assert [s.id for s in build_sources()] == [s.id for s in build_sources()]
    assert [b.id for b in build_beliefs(32)] == [b.id for b in build_beliefs(32)]
    assert [e.id for e in build_edges()] == [e.id for e in build_edges()]


def test_edges_cover_every_source_and_derivation_link():
    edges = build_edges()
    pairs = {(e.parent_id, e.child_id) for e in edges}
    for spec in S.BELIEF_SPECS:
        for source_id in spec.source_ids:
            assert (source_id, spec.id) in pairs
        for parent in spec.derived_from:
            assert (parent, spec.id) in pairs


async def test_plant_is_idempotent(planted: LocalStore):
    """Re-planting without a wipe converges rather than duplicating the graph."""
    from antivenom.attack.seed import plant

    before_beliefs = len(planted.beliefs)
    before_edges = len(planted.edges)
    await plant(planted, wipe=False)
    assert len(planted.beliefs) == before_beliefs
    assert len(planted.edges) == before_edges


async def test_planted_store_matches_the_fixture(planted: LocalStore):
    assert len(planted.beliefs) == len(S.BELIEF_SPECS)
    assert len(planted.sources) == len(S.SOURCE_SPECS)
    assert len(planted.decisions) == len(S.DECISION_SPECS)
    planted.assert_dag()
