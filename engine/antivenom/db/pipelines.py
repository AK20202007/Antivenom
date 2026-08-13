"""Aggregation pipelines, as pure functions.

Every function here returns a plain list of stage dicts and touches no driver.
That is deliberate: it means the surgery's query logic is unit-testable with no
Atlas connection, on a laptop, offline, in milliseconds. Lane A can iterate on
the traversal without burning venue WiFi.

Syntax verified against the MongoDB manual for ``$graphLookup`` and the Atlas
Vector Search reference for ``$vectorSearch``. If you change a stage, update the
matching test in ``tests/test_pipelines.py`` — those tests are the guard against
a typo that only shows up on stage.
"""

from __future__ import annotations

from typing import Any

from ..schemas import EdgeType

__all__ = [
    "BELIEFS",
    "DECISIONS",
    "PROVENANCE",
    "SOURCES",
    "SURGERIES",
    "VECTOR_INDEX_NAME",
    "as_of_filter",
    "blast_radius_pipeline",
    "contradiction_pipeline",
    "decisions_touching_pipeline",
    "independent_support_pipeline",
    "live_filter",
    "vector_index_definition",
    "vector_search_pipeline",
]

SOURCES = "sources"
BELIEFS = "beliefs"
PROVENANCE = "provenance"
DECISIONS = "decisions"
SURGERIES = "surgeries"

VECTOR_INDEX_NAME = "belief_embedding_idx"


# ─── bitemporal predicates ───────────────────────────────────────────────────


def live_filter() -> dict[str, Any]:
    """Beliefs the agent currently holds. Retrieval must always apply this, or a
    surgically removed belief keeps steering decisions."""
    return {"invalidated_at": None}


def as_of_filter(t: float) -> dict[str, Any]:
    """ "What did it believe on day N."

    Recorded by then, and either never invalidated or invalidated after then.
    Run the identical query before and after surgery and the two answers are the
    before/after proof.
    """
    return {
        "recorded_at": {"$lte": t},
        "$or": [{"invalidated_at": None}, {"invalidated_at": {"$gt": t}}],
    }


# ─── the surgery: forward traversal of the provenance DAG ────────────────────


def blast_radius_pipeline(culprit_id: str, max_depth: int) -> list[dict[str, Any]]:
    """Every belief descended from ``culprit_id``, ordered by depth.

    Walks *forward*: start at the culprit, follow ``parent_id -> child_id``
    repeatedly. ``connectFromField`` is the field whose value we chase onward and
    ``connectToField`` is the field we match it against, so chasing children
    means connectFrom=``child_id`` and connectTo=``parent_id``.

    ``maxDepth`` is inclusive and zero-based: ``maxDepth: 0`` is a plain
    non-recursive lookup returning only direct children, so a configured depth
    of N maps to ``maxDepth: N - 1``.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1 to return direct children")

    return [
        {"$match": {"parent_id": culprit_id}},
        {
            "$graphLookup": {
                "from": PROVENANCE,
                "startWith": "$child_id",
                "connectFromField": "child_id",
                "connectToField": "parent_id",
                "as": "descendants",
                "maxDepth": max_depth - 1,
                "depthField": "depth",
            }
        },
        # Fold the seed edge in with the traversal so depth 0 is the direct child.
        {
            "$project": {
                "_id": 0,
                "lineage": {
                    "$concatArrays": [
                        [
                            {
                                "belief_id": "$child_id",
                                "parent_id": "$parent_id",
                                "edge_type": "$edge_type",
                                "depth": 0,
                            }
                        ],
                        {
                            "$map": {
                                "input": "$descendants",
                                "as": "d",
                                "in": {
                                    "belief_id": "$$d.child_id",
                                    "parent_id": "$$d.parent_id",
                                    "edge_type": "$$d.edge_type",
                                    "depth": {"$add": ["$$d.depth", 1]},
                                },
                            }
                        },
                    ]
                },
            }
        },
        {"$unwind": "$lineage"},
        {"$replaceRoot": {"newRoot": "$lineage"}},
        # A belief reachable by several paths keeps its shallowest depth, so the
        # cascade animates it once, at the moment it is first infected.
        {
            "$group": {
                "_id": "$belief_id",
                "depth": {"$min": "$depth"},
                "parent_id": {"$first": "$parent_id"},
                "edge_type": {"$first": "$edge_type"},
            }
        },
        {"$project": {"_id": 0, "belief_id": "$_id", "depth": 1, "parent_id": 1, "edge_type": 1}},
        {"$sort": {"depth": 1, "belief_id": 1}},
    ]


def independent_support_pipeline(
    belief_id: str, excluded_source_ids: list[str]
) -> list[dict[str, Any]]:
    """Count the clean, non-invalidated sources still licensing a belief.

    ``excluded_source_ids`` is the poisoned lineage. What remains is independent
    support, and support at or above ``SUPPORT_THRESHOLD`` is what lets a
    descendant survive the cascade. This query is the difference between a
    dissection and a delete.
    """
    return [
        {"$match": {"_id": belief_id}},
        {
            "$lookup": {
                "from": SOURCES,
                "localField": "source_ids",
                "foreignField": "_id",
                "as": "sources",
                "pipeline": [{"$match": {"_id": {"$nin": excluded_source_ids}}}],
            }
        },
        {
            "$project": {
                "_id": 1,
                "support_count": {"$size": "$sources"},
                "corroborating_source_ids": "$sources._id",
                "mean_trust": {"$avg": "$sources.trust_prior"},
            }
        },
    ]


def decisions_touching_pipeline(belief_ids: list[str]) -> list[dict[str, Any]]:
    """Which decisions retrieved any belief in the blast radius, and over what
    span. Feeds the "14 beliefs, 3 decisions, 19 days" line."""
    return [
        {"$match": {"retrieved_belief_ids": {"$in": belief_ids}}},
        {
            "$group": {
                "_id": None,
                "decision_ids": {"$addToSet": "$_id"},
                "harmful": {"$sum": {"$cond": [{"$eq": ["$outcome", "harmful"]}, 1, 0]}},
                "first_ts": {"$min": "$timestamp"},
                "last_ts": {"$max": "$timestamp"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "decision_ids": 1,
                "harmful": 1,
                "span_days": {"$divide": [{"$subtract": ["$last_ts", "$first_ts"]}, 86400]},
            }
        },
    ]


# ─── vector search: retrieval, contradiction, ablation anomaly ───────────────


def vector_index_definition(dims: int) -> dict[str, Any]:
    """Atlas Vector Search index definition for ``beliefs.embedding``.

    ``invalidated_at`` is a filter field so retrieval can pre-filter to live
    beliefs *inside* ``$vectorSearch``. Filtering after the stage would let
    excised beliefs consume the candidate budget and silently degrade recall
    right after a surgery, which is exactly when it must not degrade.
    """
    return {
        "fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dims, "similarity": "cosine"},
            {"type": "filter", "path": "invalidated_at"},
            {"type": "filter", "path": "recorded_at"},
        ]
    }


def vector_search_pipeline(
    query_vector: list[float],
    limit: int = 8,
    *,
    live_only: bool = True,
    num_candidates: int | None = None,
    exclude_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Semantic retrieval over beliefs.

    ``exclude_ids`` is how ablation runs a counterfactual: drop one belief from
    the retrieved context and re-decide. ``num_candidates`` defaults to 20x the
    limit, the ratio Atlas recommends for ~90-95% recall against exact search.
    """
    # Over-fetch when filtering, because the definitive live check happens after
    # the stage and will discard some of what comes back.
    effective_limit = limit * 4 if live_only else limit
    stage: dict[str, Any] = {
        "index": VECTOR_INDEX_NAME,
        "path": "embedding",
        "queryVector": query_vector,
        "numCandidates": num_candidates if num_candidates is not None else effective_limit * 20,
        "limit": effective_limit,
    }
    if live_only:
        # Best-effort pre-filter. Atlas Vector Search filters are unreliable on
        # null equality, so this narrows the candidate set but is NOT the
        # guarantee. The $match below is.
        stage["filter"] = live_filter()

    pipeline: list[dict[str, Any]] = [{"$vectorSearch": stage}]
    if live_only:
        # The guarantee. Retrieval that serves an excised belief means the
        # post-surgery answer never changes and the whole payoff evaporates,
        # so this is enforced in the pipeline rather than trusted to the index.
        pipeline.append({"$match": live_filter()})
    if exclude_ids:
        pipeline.append({"$match": {"_id": {"$nin": exclude_ids}}})
    pipeline.append({"$limit": limit})
    pipeline.append(
        {
            "$project": {
                "_id": 1,
                "text": 1,
                "confidence": 1,
                "source_ids": 1,
                "support_count": 1,
                "recorded_at": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        }
    )
    return pipeline


def contradiction_pipeline(
    belief_id: str, embedding: list[float], limit: int = 10
) -> list[dict[str, Any]]:
    """Semantic neighbours of a belief, excluding itself.

    Two uses. As a contradiction detector: a belief sitting among near-identical
    neighbours that assert something incompatible is suspect. And as the
    structural-anomaly term in ablation: distance from the neighbourhood centroid
    is what separates a merely influential belief from a planted one.
    """
    return [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": limit * 20,
                "limit": limit + 1,
                "filter": live_filter(),
            }
        },
        {"$match": {"_id": {"$ne": belief_id}}},
        {
            "$project": {
                "_id": 1,
                "text": 1,
                "embedding": 1,
                "source_ids": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
        {"$limit": limit},
    ]


# ─── index bootstrap ─────────────────────────────────────────────────────────

STANDARD_INDEXES: dict[str, list[tuple[list[tuple[str, int]], dict[str, Any]]]] = {
    # $graphLookup performance depends entirely on connectToField being indexed.
    PROVENANCE: [
        ([("parent_id", 1)], {"name": "parent_idx"}),
        ([("child_id", 1)], {"name": "child_idx"}),
        ([("parent_id", 1), ("child_id", 1)], {"name": "edge_unique_idx", "unique": True}),
    ],
    BELIEFS: [
        ([("invalidated_at", 1)], {"name": "live_idx"}),
        ([("recorded_at", -1)], {"name": "recorded_idx"}),
        ([("source_ids", 1)], {"name": "source_idx"}),
        ([("derived_from", 1)], {"name": "derived_idx"}),
    ],
    DECISIONS: [
        ([("retrieved_belief_ids", 1)], {"name": "retrieved_idx"}),
        ([("timestamp", -1)], {"name": "ts_idx"}),
        ([("outcome", 1)], {"name": "outcome_idx"}),
    ],
    SOURCES: [
        ([("channel", 1)], {"name": "channel_idx"}),
    ],
    SURGERIES: [
        ([("decision_id", 1)], {"name": "decision_idx"}),
    ],
}


def change_stream_pipeline() -> list[dict[str, Any]]:
    """Watch for invalidation, so the database drives the cascade.

    When a belief is invalidated this fires, children get re-evaluated, and the
    dashboard receives the event. The app does not poll — that is the point of
    using change streams rather than a loop.
    """
    return [
        {
            "$match": {
                "operationType": {"$in": ["update", "replace"]},
                "updateDescription.updatedFields.invalidated_at": {"$ne": None},
            }
        }
    ]


def edge_type_for(parent_is_source: bool) -> EdgeType:
    return EdgeType.EXTRACTED if parent_is_source else EdgeType.DERIVED
