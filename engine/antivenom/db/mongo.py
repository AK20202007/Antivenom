"""Atlas backend.

Wired against the pipelines in :mod:`antivenom.db.pipelines`. The pipeline
*shapes* are unit-tested offline; what still needs a live cluster is the vector
index, which Atlas builds asynchronously and which cannot be created through the
data API on all tiers.

**Before the first run:** create the vector index named ``belief_embedding_idx``
on ``beliefs.embedding`` using the definition from
:func:`~antivenom.db.pipelines.vector_index_definition`, either in the Atlas UI
or via ``antivenom db init``. Vector search silently returns nothing until the
index finishes building, which reads exactly like "retrieval is broken".
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from ..config import settings
from ..schemas import Belief, BlastNode, Decision, ProvenanceEdge, Source, Surgery
from . import pipelines as P

if TYPE_CHECKING:  # pragma: no cover
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class MongoStore:
    """Implements :class:`~antivenom.db.base.Store` against MongoDB Atlas."""

    def __init__(self, uri: str | None = None, db_name: str | None = None) -> None:
        cfg = settings()
        self._uri = uri or cfg.mongodb_uri
        self._db_name = db_name or cfg.mongodb_db
        self._client: AsyncIOMotorClient[Any] | None = None
        self._db: AsyncIOMotorDatabase[Any] | None = None

    # ─── lifecycle ───────────────────────────────────────────────────────────

    @property
    def db(self) -> AsyncIOMotorDatabase[Any]:
        if self._db is None:
            raise RuntimeError("MongoStore.connect() has not been awaited")
        return self._db

    async def connect(self) -> None:
        from motor.motor_asyncio import AsyncIOMotorClient

        if not self._uri:
            raise RuntimeError(
                "MONGODB_URI is empty. Point it at the Atlas Hackathon Sandbox cluster "
                "or run with ANTIVENOM_FEATURE_MONGO=0."
            )
        self._client = AsyncIOMotorClient(self._uri, serverSelectionTimeoutMS=8000, tz_aware=False)
        self._db = self._client[self._db_name]
        await self._db.command("ping")

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None

    async def ensure_indexes(self) -> None:
        for collection, specs in P.STANDARD_INDEXES.items():
            for keys, opts in specs:
                await self.db[collection].create_index(keys, **opts)

    async def drop_all(self) -> None:
        for collection in (P.SOURCES, P.BELIEFS, P.PROVENANCE, P.DECISIONS, P.SURGERIES):
            await self.db[collection].delete_many({})

    # ─── writes ──────────────────────────────────────────────────────────────

    async def put_source(self, source: Source) -> None:
        doc = source.to_mongo()
        await self.db[P.SOURCES].replace_one({"_id": source.id}, doc, upsert=True)

    async def put_belief(self, belief: Belief) -> None:
        doc = belief.to_mongo()
        await self.db[P.BELIEFS].replace_one({"_id": belief.id}, doc, upsert=True)

    async def put_edge(self, edge: ProvenanceEdge) -> None:
        doc = edge.to_mongo()
        await self.db[P.PROVENANCE].replace_one({"_id": edge.id}, doc, upsert=True)

    async def put_decision(self, decision: Decision) -> None:
        doc = decision.to_mongo()
        await self.db[P.DECISIONS].replace_one({"_id": decision.id}, doc, upsert=True)

    async def put_surgery(self, surgery: Surgery) -> None:
        doc = surgery.to_mongo()
        await self.db[P.SURGERIES].replace_one({"_id": surgery.id}, doc, upsert=True)

    async def invalidate_belief(self, belief_id: str, reason: str, at: float) -> bool:
        """Conditional on ``invalidated_at: None`` so a re-run cannot overwrite
        the original timestamp. The audit row records when it actually happened,
        not when someone last replayed the cascade."""
        result = await self.db[P.BELIEFS].update_one(
            {"_id": belief_id, "invalidated_at": None},
            {"$set": {"invalidated_at": at, "invalidation_reason": reason}},
        )
        return result.modified_count == 1

    async def set_trust(self, source_id: str, trust: float) -> None:
        await self.db[P.SOURCES].update_one(
            {"_id": source_id}, {"$set": {"trust_prior": max(0.0, min(1.0, trust))}}
        )

    # ─── reads ───────────────────────────────────────────────────────────────

    async def get_belief(self, belief_id: str) -> Belief | None:
        doc = await self.db[P.BELIEFS].find_one({"_id": belief_id})
        return Belief.from_mongo(doc) if doc else None

    async def get_source(self, source_id: str) -> Source | None:
        doc = await self.db[P.SOURCES].find_one({"_id": source_id})
        return Source.from_mongo(doc) if doc else None

    async def get_decision(self, decision_id: str) -> Decision | None:
        doc = await self.db[P.DECISIONS].find_one({"_id": decision_id})
        return Decision.from_mongo(doc) if doc else None

    async def live_beliefs(self) -> list[Belief]:
        cursor = self.db[P.BELIEFS].find(P.live_filter())
        return [Belief.from_mongo(d) async for d in cursor]

    async def beliefs_as_of(self, t: float) -> list[Belief]:
        cursor = self.db[P.BELIEFS].find(P.as_of_filter(t))
        return [Belief.from_mongo(d) async for d in cursor]

    # ─── traversal ───────────────────────────────────────────────────────────

    async def blast_radius(self, culprit_id: str, max_depth: int) -> list[BlastNode]:
        cursor = self.db[P.PROVENANCE].aggregate(P.blast_radius_pipeline(culprit_id, max_depth))
        nodes = [BlastNode.model_validate(d) async for d in cursor]
        return [n for n in nodes if n.belief_id != culprit_id]

    async def independent_support(
        self, belief_id: str, excluded_source_ids: list[str]
    ) -> tuple[int, list[str]]:
        cursor = self.db[P.BELIEFS].aggregate(
            P.independent_support_pipeline(belief_id, excluded_source_ids)
        )
        async for doc in cursor:
            return int(doc.get("support_count", 0)), sorted(doc.get("corroborating_source_ids", []))
        return 0, []

    async def decisions_touching(self, belief_ids: list[str]) -> list[Decision]:
        cursor = (
            self.db[P.DECISIONS]
            .find({"retrieved_belief_ids": {"$in": belief_ids}})
            .sort("timestamp", 1)
        )
        return [Decision.from_mongo(d) async for d in cursor]

    async def vector_search(
        self,
        query_vector: list[float],
        limit: int = 8,
        *,
        exclude_ids: list[str] | None = None,
        live_only: bool = True,
    ) -> list[tuple[Belief, float]]:
        cursor = self.db[P.BELIEFS].aggregate(
            P.vector_search_pipeline(
                query_vector, limit=limit, live_only=live_only, exclude_ids=exclude_ids
            )
        )
        out: list[tuple[Belief, float]] = []
        async for doc in cursor:
            score = float(doc.pop("score", 0.0))
            full = await self.db[P.BELIEFS].find_one({"_id": doc["_id"]})
            if full:
                out.append((Belief.from_mongo(full), score))
        return out

    async def neighbours(self, belief_id: str, limit: int = 10) -> list[tuple[Belief, float]]:
        belief = await self.get_belief(belief_id)
        if belief is None or not belief.embedding:
            return []
        cursor = self.db[P.BELIEFS].aggregate(
            P.contradiction_pipeline(belief_id, belief.embedding, limit=limit)
        )
        out: list[tuple[Belief, float]] = []
        async for doc in cursor:
            score = float(doc.pop("score", 0.0))
            full = await self.db[P.BELIEFS].find_one({"_id": doc["_id"]})
            if full:
                out.append((Belief.from_mongo(full), score))
        return out

    # ─── reactive ────────────────────────────────────────────────────────────

    async def watch_invalidations(self) -> AsyncIterator[str]:
        """Change stream on ``beliefs``. The database drives the cascade.

        Requires a replica set, which every Atlas cluster is — but a standalone
        local ``mongod`` is not, so this raises there. Use the local store for
        offline work rather than trying to make a standalone emit change events.
        """
        async with self.db[P.BELIEFS].watch(P.change_stream_pipeline()) as stream:
            async for change in stream:
                doc_key = change.get("documentKey") or {}
                belief_id = doc_key.get("_id")
                if belief_id:
                    yield str(belief_id)

    # ─── bootstrap ───────────────────────────────────────────────────────────

    async def create_vector_index(self) -> str:
        """Create the Atlas vector index if the cluster tier allows it.

        Returns the index name. Atlas builds it asynchronously — poll
        ``$listSearchIndexes`` until ``queryable`` is true before relying on
        retrieval, or the first demo query comes back empty.
        """
        definition = P.vector_index_definition(settings().embedding_dims)
        await self.db[P.BELIEFS].create_search_index(
            {"name": P.VECTOR_INDEX_NAME, "type": "vectorSearch", "definition": definition}
        )
        return P.VECTOR_INDEX_NAME

    async def vector_index_ready(self) -> bool:
        cursor = await self.db[P.BELIEFS].list_search_indexes(P.VECTOR_INDEX_NAME)
        async for idx in cursor:
            return bool(idx.get("queryable"))
        return False
