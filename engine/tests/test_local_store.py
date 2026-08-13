"""The in-memory store is the demo floor, so it is tested like production."""

from __future__ import annotations

from antivenom.attack import scenario as S
from antivenom.db.local import LocalStore, cosine
from antivenom.schemas import Belief, EdgeType, ProvenanceEdge


async def test_blast_radius_excludes_patient_zero(planted: LocalStore):
    nodes = await planted.blast_radius(S.PATIENT_ZERO, max_depth=8)
    ids = [n.belief_id for n in nodes]
    assert S.PATIENT_ZERO not in ids, "the culprit is coloured separately by the UI"


async def test_blast_radius_finds_the_whole_lineage(planted: LocalStore):
    nodes = await planted.blast_radius(S.PATIENT_ZERO, max_depth=8)
    found = {n.belief_id for n in nodes}
    expected = {b.id for b in S.BELIEF_SPECS if b.in_lineage and b.id != S.PATIENT_ZERO}
    assert found == expected


async def test_blast_radius_is_ordered_by_depth(planted: LocalStore):
    nodes = await planted.blast_radius(S.PATIENT_ZERO, max_depth=8)
    depths = [n.depth for n in nodes]
    assert depths == sorted(depths), "the radius must expand outward on screen"


async def test_blast_radius_is_deterministic(planted: LocalStore):
    first = await planted.blast_radius(S.PATIENT_ZERO, max_depth=8)
    second = await planted.blast_radius(S.PATIENT_ZERO, max_depth=8)
    assert [n.belief_id for n in first] == [n.belief_id for n in second]


async def test_blast_radius_respects_max_depth(planted: LocalStore):
    shallow = await planted.blast_radius(S.PATIENT_ZERO, max_depth=1)
    assert {n.depth for n in shallow} == {0}
    deep = await planted.blast_radius(S.PATIENT_ZERO, max_depth=8)
    assert len(deep) > len(shallow)


async def test_diamond_lineage_keeps_shallowest_depth(store: LocalStore):
    """A belief reachable by two paths animates once, when first infected."""
    for bid in ("a", "b", "c", "d"):
        await store.put_belief(Belief(_id=bid, text=bid))
    for parent, child in (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")):
        await store.put_edge(ProvenanceEdge.between(parent, child, EdgeType.DERIVED))
    # Add a long way round to d, to prove min-depth wins over discovery order.
    await store.put_belief(Belief(_id="e", text="e"))
    await store.put_edge(ProvenanceEdge.between("c", "e", EdgeType.DERIVED))
    await store.put_edge(ProvenanceEdge.between("e", "d", EdgeType.DERIVED))

    nodes = {n.belief_id: n.depth for n in await store.blast_radius("a", max_depth=8)}
    assert nodes == {"b": 0, "c": 0, "d": 1, "e": 1}


async def test_blast_radius_of_unknown_node_is_empty(store: LocalStore):
    assert await store.blast_radius("nope", max_depth=4) == []


async def test_independent_support_drops_the_poisoned_source(planted: LocalStore):
    count, sources = await planted.independent_support("blf_maintsat", [S.POISONED_SOURCE_ID])
    assert count == 2, "runbook and handbook both state the window"
    assert S.POISONED_SOURCE_ID not in sources


async def test_a_belief_with_only_the_poison_has_no_support(planted: LocalStore):
    count, sources = await planted.independent_support("blf_endpoint", [S.POISONED_SOURCE_ID])
    assert count == 0
    assert sources == []


async def test_invalidate_stamps_and_is_not_a_delete(planted: LocalStore):
    assert await planted.invalidate_belief("blf_endpoint", "test", at=500.0)
    belief = await planted.get_belief("blf_endpoint")
    assert belief is not None, "invalidation must never remove the document"
    assert belief.invalidated_at == 500.0
    assert not belief.is_live


async def test_reinvalidating_returns_false(planted: LocalStore):
    await planted.invalidate_belief("blf_endpoint", "first", at=500.0)
    assert await planted.invalidate_belief("blf_endpoint", "second", at=600.0) is False


async def test_live_beliefs_excludes_invalidated(planted: LocalStore):
    before = len(await planted.live_beliefs())
    await planted.invalidate_belief("blf_endpoint", "test", at=500.0)
    assert len(await planted.live_beliefs()) == before - 1


async def test_beliefs_as_of_answers_before_and_after(planted: LocalStore):
    surgery_time = S.EPOCH + 30 * S.DAY
    before = {b.id for b in await planted.beliefs_as_of(surgery_time)}
    assert "blf_endpoint" in before

    await planted.invalidate_belief("blf_endpoint", "excised", at=surgery_time + 1)
    still_before = {b.id for b in await planted.beliefs_as_of(surgery_time)}
    after = {b.id for b in await planted.beliefs_as_of(surgery_time + 100)}

    assert "blf_endpoint" in still_before, "history must not be rewritten"
    assert "blf_endpoint" not in after


async def test_vector_search_excludes_invalidated_by_default(planted: LocalStore):
    target = await planted.get_belief("blf_endpoint")
    assert target is not None
    hits = await planted.vector_search(target.embedding, limit=5)
    assert "blf_endpoint" in {b.id for b, _ in hits}

    await planted.invalidate_belief("blf_endpoint", "excised", at=500.0)
    hits = await planted.vector_search(target.embedding, limit=5)
    assert "blf_endpoint" not in {b.id for b, _ in hits}, (
        "retrieval that ignores invalidated_at keeps serving excised beliefs and "
        "the post-surgery answer never changes"
    )


async def test_vector_search_honours_exclude_ids(planted: LocalStore):
    """This is how ablation runs a counterfactual."""
    target = await planted.get_belief("blf_endpoint")
    assert target is not None
    hits = await planted.vector_search(target.embedding, limit=5, exclude_ids=["blf_endpoint"])
    assert "blf_endpoint" not in {b.id for b, _ in hits}


async def test_vector_search_ranking_is_stable(planted: LocalStore):
    target = await planted.get_belief("blf_maintsat")
    assert target is not None
    a = [b.id for b, _ in await planted.vector_search(target.embedding, limit=6)]
    b = [b.id for b, _ in await planted.vector_search(target.embedding, limit=6)]
    assert a == b


async def test_neighbours_excludes_self(planted: LocalStore):
    hits = await planted.neighbours("blf_maintsat", limit=5)
    assert "blf_maintsat" not in {b.id for b, _ in hits}


async def test_decisions_touching(planted: LocalStore):
    found = await planted.decisions_touching([S.PATIENT_ZERO])
    assert [d.id for d in found] == [S.TRIGGER_DECISION_ID]


async def test_provenance_stays_acyclic(planted: LocalStore):
    """A cycle makes the blast radius never terminate — a hung demo."""
    planted.assert_dag()


async def test_snapshot_roundtrip(planted: LocalStore):
    payload = planted.snapshot()
    fresh = LocalStore()
    await fresh.load_snapshot(payload)
    assert len(fresh.beliefs) == len(planted.beliefs)
    assert len(fresh.edges) == len(planted.edges)
    original = await planted.blast_radius(S.PATIENT_ZERO, max_depth=8)
    restored = await fresh.blast_radius(S.PATIENT_ZERO, max_depth=8)
    assert [n.belief_id for n in original] == [n.belief_id for n in restored]


def test_cosine_handles_degenerate_vectors():
    """An un-embedded belief must rank last, not crash retrieval mid-demo."""
    assert cosine([], [1.0]) == 0.0
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine([1.0, 2.0], [1.0]) == 0.0
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == -1.0
