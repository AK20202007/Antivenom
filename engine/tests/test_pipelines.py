"""Pipeline shapes, tested with no cluster attached.

These guard against the class of typo that only shows up on stage: a swapped
connectFrom/connectToField silently walks the graph backwards and returns an
empty blast radius, which looks exactly like "the poison had no children".
"""

from __future__ import annotations

import pytest

from antivenom.db import pipelines as P


def _stage(pipeline: list[dict], name: str) -> dict:
    return next(s[name] for s in pipeline if name in s)


def test_blast_radius_walks_forward_down_the_lineage():
    stage = _stage(P.blast_radius_pipeline("blf_p", 6), "$graphLookup")
    assert stage["from"] == P.PROVENANCE
    assert stage["startWith"] == "$child_id"
    # Chasing children means connectFrom=child_id, connectTo=parent_id. Swapping
    # these walks toward ancestors and finds nothing.
    assert stage["connectFromField"] == "child_id"
    assert stage["connectToField"] == "parent_id"
    assert stage["depthField"] == "depth"


def test_blast_radius_maxdepth_is_zero_based():
    """maxDepth is inclusive and zero-based, so N levels means maxDepth N-1."""
    assert _stage(P.blast_radius_pipeline("x", 6), "$graphLookup")["maxDepth"] == 5
    assert _stage(P.blast_radius_pipeline("x", 1), "$graphLookup")["maxDepth"] == 0


def test_blast_radius_rejects_zero_depth():
    with pytest.raises(ValueError):
        P.blast_radius_pipeline("x", 0)


def test_blast_radius_seeds_from_direct_children():
    pipeline = P.blast_radius_pipeline("blf_p", 4)
    assert pipeline[0] == {"$match": {"parent_id": "blf_p"}}


def test_blast_radius_dedupes_to_shallowest_depth():
    group = _stage(P.blast_radius_pipeline("x", 4), "$group")
    assert group["_id"] == "$belief_id"
    assert group["depth"] == {"$min": "$depth"}


def test_blast_radius_sorts_by_depth():
    sort = _stage(P.blast_radius_pipeline("x", 4), "$sort")
    assert next(iter(sort.keys())) == "depth"


def test_live_filter_is_null_not_missing():
    """`{"invalidated_at": None}` matches both null and absent, which is what we
    want; `{"$exists": False}` would miss explicitly-null documents."""
    assert P.live_filter() == {"invalidated_at": None}


def test_as_of_filter_covers_both_bitemporal_halves():
    f = P.as_of_filter(1000.0)
    assert f["recorded_at"] == {"$lte": 1000.0}
    assert {"invalidated_at": None} in f["$or"]
    assert {"invalidated_at": {"$gt": 1000.0}} in f["$or"]


def test_vector_search_is_the_first_stage():
    """Atlas requires it; anything before it is a hard error at query time."""
    pipeline = P.vector_search_pipeline([0.1] * 8, limit=5)
    assert "$vectorSearch" in pipeline[0]


def test_vector_search_prefilters_to_live_beliefs():
    """Filtering after the stage lets excised beliefs eat the candidate budget
    and degrades recall right after a surgery."""
    stage = _stage(P.vector_search_pipeline([0.1] * 8, limit=5), "$vectorSearch")
    assert stage["filter"] == P.live_filter()


def test_vector_search_over_fetches_when_filtering_to_live():
    """The definitive live check happens after the stage, so the stage has to
    return more than the caller asked for or the post-filter starves it."""
    stage = _stage(P.vector_search_pipeline([0.1] * 8, limit=5), "$vectorSearch")
    assert stage["limit"] > 5
    assert stage["numCandidates"] == stage["limit"] * 20


def test_vector_search_num_candidates_is_twenty_times_the_stage_limit():
    stage = _stage(P.vector_search_pipeline([0.1] * 8, limit=5, live_only=False), "$vectorSearch")
    assert stage["limit"] == 5
    assert stage["numCandidates"] == 100


def test_live_filtering_is_enforced_after_the_stage_not_trusted_to_the_index():
    """Atlas vector-search filters are unreliable on null equality. Serving an
    excised belief means the post-surgery answer never changes, so the guarantee
    is a $match in the pipeline rather than the index filter."""
    pipeline = P.vector_search_pipeline([0.1] * 8, limit=5)
    assert {"$match": P.live_filter()} in pipeline
    # And the caller still gets exactly what it asked for.
    assert {"$limit": 5} in pipeline


def test_vector_search_projects_the_score():
    project = _stage(P.vector_search_pipeline([0.1] * 8), "$project")
    assert project["score"] == {"$meta": "vectorSearchScore"}


def test_vector_search_exclusion_is_how_ablation_runs_counterfactuals():
    pipeline = P.vector_search_pipeline([0.1] * 8, exclude_ids=["blf_x"])
    assert {"$match": {"_id": {"$nin": ["blf_x"]}}} in pipeline


def test_vector_index_definition_matches_the_filters_we_use():
    definition = P.vector_index_definition(1536)
    vector = next(f for f in definition["fields"] if f["type"] == "vector")
    assert vector["numDimensions"] == 1536
    assert vector["similarity"] == "cosine"
    filters = {f["path"] for f in definition["fields"] if f["type"] == "filter"}
    assert "invalidated_at" in filters, "the live pre-filter needs this indexed"


def test_independent_support_excludes_the_poisoned_sources():
    pipeline = P.independent_support_pipeline("blf_x", ["src_bad"])
    lookup = _stage(pipeline, "$lookup")
    assert lookup["from"] == P.SOURCES
    assert lookup["pipeline"] == [{"$match": {"_id": {"$nin": ["src_bad"]}}}]


def test_contradiction_pipeline_excludes_the_belief_itself():
    pipeline = P.contradiction_pipeline("blf_x", [0.1] * 8, limit=5)
    assert {"$match": {"_id": {"$ne": "blf_x"}}} in pipeline


def test_change_stream_watches_invalidation_only():
    match = _stage(P.change_stream_pipeline(), "$match")
    assert match["updateDescription.updatedFields.invalidated_at"] == {"$ne": None}


def test_graphlookup_connect_field_is_indexed():
    """$graphLookup performance collapses without an index on connectToField."""
    indexed = {keys[0][0] for keys, _ in P.STANDARD_INDEXES[P.PROVENANCE]}
    assert "parent_id" in indexed
    assert "child_id" in indexed


def test_retrieval_field_is_indexed_for_ablation_lookups():
    indexed = {keys[0][0] for keys, _ in P.STANDARD_INDEXES[P.DECISIONS]}
    assert "retrieved_belief_ids" in indexed
