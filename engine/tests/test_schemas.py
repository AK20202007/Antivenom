from __future__ import annotations

import pytest
from pydantic import ValidationError

from antivenom.schemas import (
    Belief,
    Channel,
    EdgeType,
    ProvenanceEdge,
    Source,
    SourceType,
    Surgery,
    new_id,
)


def test_new_id_is_deterministic():
    """Re-seeding between judge visits must reproduce identical ids, or the
    cascade animates differently the second time."""
    assert new_id("blf", "a", 1) == new_id("blf", "a", 1)
    assert new_id("blf", "a", 1) != new_id("blf", "a", 2)
    assert new_id("blf", "x").startswith("blf_")


def test_new_id_separator_prevents_collision():
    """('ab','c') and ('a','bc') must not hash to the same id."""
    assert new_id("blf", "ab", "c") != new_id("blf", "a", "bc")


def test_belief_rejects_empty_text():
    with pytest.raises(ValidationError):
        Belief(_id="blf_1", text="   ")


def test_invalidation_requires_a_reason():
    """An invalidated belief with no reason is an unauditable delete, and the
    audit row is the whole point of not deleting."""
    with pytest.raises(ValidationError):
        Belief(_id="blf_1", text="x", invalidated_at=100.0)
    with pytest.raises(ValidationError):
        Belief(_id="blf_1", text="x", invalidation_reason="because")


def test_invalidate_is_idempotent():
    b = Belief(_id="blf_1", text="x")
    b.invalidate("first", at=10.0)
    b.invalidate("second", at=20.0)
    assert b.invalidated_at == 10.0
    assert b.invalidation_reason == "first"


def test_was_live_at_is_the_bitemporal_proof():
    b = Belief(_id="blf_1", text="x", recorded_at=100.0)
    assert not b.was_live_at(99.0)  # not learned yet
    assert b.was_live_at(150.0)

    b.invalidate("excised", at=200.0)
    assert b.was_live_at(150.0)  # still true before surgery
    assert not b.was_live_at(250.0)  # gone after
    assert not b.is_live


def test_edge_rejects_self_loop():
    with pytest.raises(ValidationError):
        ProvenanceEdge(_id="e", parent_id="a", child_id="a", edge_type=EdgeType.DERIVED)


def test_edge_between_is_deterministic():
    a = ProvenanceEdge.between("p", "c", EdgeType.DERIVED)
    b = ProvenanceEdge.between("p", "c", EdgeType.DERIVED)
    assert a.id == b.id


def test_surgery_partition_must_be_disjoint():
    """A belief that both survives and is excised means the walk double-counted,
    which silently corrupts RR and CD."""
    with pytest.raises(ValidationError):
        Surgery(
            _id="sur_1",
            decision_id="dec_1",
            culprit_id="blf_1",
            excised=["blf_2"],
            survived=["blf_2"],
        )


def test_mongo_roundtrip_preserves_the_id_alias():
    source = Source(_id="src_1", type=SourceType.IMAGE, uri="seed://x", channel=Channel.UPLOAD)
    doc = source.to_mongo()
    assert doc["_id"] == "src_1"
    assert "id" not in doc
    assert Source.from_mongo(doc) == source


def test_extra_fields_are_rejected():
    """Smuggling an extra key through a dict is how lane contracts rot."""
    with pytest.raises(ValidationError):
        Belief(_id="blf_1", text="x", sneaky_field=True)
