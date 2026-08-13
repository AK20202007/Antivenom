"""The store interface both backends implement.

Two implementations, one interface:

* :class:`~antivenom.db.mongo.MongoStore` — Atlas. ``$graphLookup`` is the
  surgery, ``$vectorSearch`` is retrieval and the contradiction detector, change
  streams drive re-evaluation.
* :class:`~antivenom.db.local.LocalStore` — an in-memory NetworkX graph with
  identical semantics, used when ``FEATURE_MONGO=0``.

The local backend is not a toy. It is the demo floor, so the same test suite
runs against both and any behavioural drift between them is a bug in whichever
one disagrees with the tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..schemas import Belief, BlastNode, Decision, ProvenanceEdge, Source, Surgery


@runtime_checkable
class Store(Protocol):
    """Persistence and traversal. Async throughout — Motor is async and the
    event server is asyncio, so a sync interface would need a thread pool on the
    demo-critical path."""

    # ─── lifecycle ───────────────────────────────────────────────────────────
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ensure_indexes(self) -> None:
        """Idempotent. Safe to call on every boot."""
        ...

    async def drop_all(self) -> None:
        """Wipe the store. Used to re-seed a fresh poisoned store between judge
        visits — the reset teammate runs this."""
        ...

    # ─── writes ──────────────────────────────────────────────────────────────
    async def put_source(self, source: Source) -> None: ...
    async def put_belief(self, belief: Belief) -> None: ...
    async def put_edge(self, edge: ProvenanceEdge) -> None: ...
    async def put_decision(self, decision: Decision) -> None: ...
    async def put_surgery(self, surgery: Surgery) -> None: ...

    async def invalidate_belief(self, belief_id: str, reason: str, at: float) -> bool:
        """Stamp ``invalidated_at``. Never deletes. Returns False if the belief
        was already invalidated, so callers can keep the cascade idempotent."""
        ...

    async def set_trust(self, source_id: str, trust: float) -> None: ...

    # ─── reads ───────────────────────────────────────────────────────────────
    async def get_belief(self, belief_id: str) -> Belief | None: ...
    async def get_source(self, source_id: str) -> Source | None: ...
    async def get_decision(self, decision_id: str) -> Decision | None: ...

    async def live_beliefs(self) -> list[Belief]:
        """Beliefs currently held — ``invalidated_at`` is null."""
        ...

    async def beliefs_as_of(self, t: float) -> list[Belief]:
        """What the agent believed at time ``t``. The before/after proof."""
        ...

    # ─── traversal ───────────────────────────────────────────────────────────
    async def blast_radius(self, culprit_id: str, max_depth: int) -> list[BlastNode]:
        """Every descendant of the culprit, ordered by depth ascending.

        A belief reachable by several paths appears once, at its shallowest
        depth. Must not include the culprit itself — patient zero is handled
        separately by the caller so the UI can colour it differently.
        """
        ...

    async def independent_support(
        self, belief_id: str, excluded_source_ids: list[str]
    ) -> tuple[int, list[str]]:
        """``(count, corroborating_source_ids)`` after excluding the poisoned
        lineage. The survival criterion."""
        ...

    async def decisions_touching(self, belief_ids: list[str]) -> list[Decision]: ...

    async def vector_search(
        self,
        query_vector: list[float],
        limit: int = 8,
        *,
        exclude_ids: list[str] | None = None,
        live_only: bool = True,
    ) -> list[tuple[Belief, float]]:
        """``(belief, score)`` ranked by cosine similarity, descending."""
        ...

    async def neighbours(self, belief_id: str, limit: int = 10) -> list[tuple[Belief, float]]:
        """Semantic neighbours excluding the belief itself. Feeds the
        structural-anomaly term in ablation and the contradiction detector."""
        ...

    # ─── reactive ────────────────────────────────────────────────────────────
    def watch_invalidations(self) -> AsyncIterator[str]:
        """Async iterator of belief ids as they are invalidated.

        On Atlas this is a change stream, which is what makes the database drive
        the cascade rather than the app polling it. The local store emits from an
        internal queue so the same code path works offline.
        """
        ...
