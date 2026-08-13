"""In-memory store — the demo floor.

Runs with ``FEATURE_MONGO=0``. Same interface, same semantics, no network. This
is what renders the cascade when the venue WiFi dies, so it is held to the same
test suite as the Atlas backend rather than treated as a stub.

NetworkX handles the provenance DAG; NumPy handles cosine similarity. Both are
already dependencies and neither needs a service.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

import networkx as nx
import numpy as np

from ..schemas import Belief, BlastNode, Decision, EdgeType, ProvenanceEdge, Source, Surgery


def cosine(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    """Cosine similarity, clamped to [-1, 1]. Zero vectors score 0 rather than
    raising, because an un-embedded belief should rank last, not crash retrieval
    thirty seconds into a demo."""
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if va.size == 0 or vb.size == 0 or va.shape != vb.shape:
        return 0.0
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.clip(np.dot(va, vb) / (na * nb), -1.0, 1.0))


class LocalStore:
    """Implements :class:`~antivenom.db.base.Store` with no external service."""

    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.beliefs: dict[str, Belief] = {}
        self.edges: dict[str, ProvenanceEdge] = {}
        self.decisions: dict[str, Decision] = {}
        self.surgeries: dict[str, Surgery] = {}
        self.graph: nx.DiGraph = nx.DiGraph()
        self._invalidations: asyncio.Queue[str] = asyncio.Queue()

    # ─── lifecycle ───────────────────────────────────────────────────────────

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ensure_indexes(self) -> None:
        return None

    async def drop_all(self) -> None:
        self.sources.clear()
        self.beliefs.clear()
        self.edges.clear()
        self.decisions.clear()
        self.surgeries.clear()
        self.graph.clear()
        self._invalidations = asyncio.Queue()

    # ─── writes ──────────────────────────────────────────────────────────────

    async def put_source(self, source: Source) -> None:
        self.sources[source.id] = source
        self.graph.add_node(source.id, kind="source")

    async def put_belief(self, belief: Belief) -> None:
        self.beliefs[belief.id] = belief
        self.graph.add_node(belief.id, kind="belief")

    async def put_edge(self, edge: ProvenanceEdge) -> None:
        self.edges[edge.id] = edge
        self.graph.add_edge(edge.parent_id, edge.child_id, edge_type=edge.edge_type)

    async def put_decision(self, decision: Decision) -> None:
        self.decisions[decision.id] = decision

    async def put_surgery(self, surgery: Surgery) -> None:
        self.surgeries[surgery.id] = surgery

    async def invalidate_belief(self, belief_id: str, reason: str, at: float) -> bool:
        belief = self.beliefs.get(belief_id)
        if belief is None or not belief.is_live:
            return False
        belief.invalidate(reason, at)
        await self._invalidations.put(belief_id)
        return True

    async def set_trust(self, source_id: str, trust: float) -> None:
        source = self.sources.get(source_id)
        if source is not None:
            source.trust_prior = max(0.0, min(1.0, trust))

    # ─── reads ───────────────────────────────────────────────────────────────

    async def get_belief(self, belief_id: str) -> Belief | None:
        return self.beliefs.get(belief_id)

    async def get_source(self, source_id: str) -> Source | None:
        return self.sources.get(source_id)

    async def get_decision(self, decision_id: str) -> Decision | None:
        return self.decisions.get(decision_id)

    async def live_beliefs(self) -> list[Belief]:
        return [b for b in self.beliefs.values() if b.is_live]

    async def beliefs_as_of(self, t: float) -> list[Belief]:
        return [b for b in self.beliefs.values() if b.was_live_at(t)]

    async def all_beliefs(self) -> list[Belief]:
        return list(self.beliefs.values())

    async def all_sources(self) -> list[Source]:
        return list(self.sources.values())

    # ─── traversal ───────────────────────────────────────────────────────────

    async def blast_radius(self, culprit_id: str, max_depth: int) -> list[BlastNode]:
        """Breadth-first forward walk. BFS rather than DFS so the first time we
        reach a node is already its shallowest depth — which is the depth the
        cascade animates at."""
        if culprit_id not in self.graph:
            return []

        seen: dict[str, BlastNode] = {}
        queue: deque[tuple[str, int, str | None]] = deque([(culprit_id, -1, None)])

        while queue:
            node_id, depth, parent_id = queue.popleft()
            if depth >= 0:
                if node_id in seen or node_id == culprit_id:
                    continue
                edge_data = self.graph.get_edge_data(parent_id, node_id) or {}
                seen[node_id] = BlastNode(
                    belief_id=node_id,
                    depth=depth,
                    parent_id=parent_id,
                    edge_type=edge_data.get("edge_type"),
                )
                if depth + 1 >= max_depth:
                    continue
            for child in self.graph.successors(node_id):
                if child not in seen and child != culprit_id:
                    queue.append((child, depth + 1, node_id))

        return sorted(seen.values(), key=lambda n: (n.depth, n.belief_id))

    async def independent_support(
        self, belief_id: str, excluded_source_ids: list[str]
    ) -> tuple[int, list[str]]:
        belief = self.beliefs.get(belief_id)
        if belief is None:
            return 0, []
        excluded = set(excluded_source_ids)
        corroborating = [
            sid for sid in belief.source_ids if sid not in excluded and sid in self.sources
        ]
        return len(corroborating), sorted(corroborating)

    async def decisions_touching(self, belief_ids: list[str]) -> list[Decision]:
        wanted = set(belief_ids)
        return sorted(
            (d for d in self.decisions.values() if wanted & set(d.retrieved_belief_ids)),
            key=lambda d: d.timestamp,
        )

    async def vector_search(
        self,
        query_vector: list[float],
        limit: int = 8,
        *,
        exclude_ids: list[str] | None = None,
        live_only: bool = True,
    ) -> list[tuple[Belief, float]]:
        excluded = set(exclude_ids or ())
        pool = [
            b
            for b in self.beliefs.values()
            if b.id not in excluded and (b.is_live or not live_only)
        ]
        scored = [(b, cosine(query_vector, b.embedding)) for b in pool]
        # Sort by score then id so ties break deterministically. Without the id
        # tiebreak the ablation candidate order drifts between runs.
        scored.sort(key=lambda pair: (-pair[1], pair[0].id))
        return scored[:limit]

    async def neighbours(self, belief_id: str, limit: int = 10) -> list[tuple[Belief, float]]:
        belief = self.beliefs.get(belief_id)
        if belief is None or not belief.embedding:
            return []
        return await self.vector_search(
            belief.embedding, limit=limit, exclude_ids=[belief_id], live_only=True
        )

    # ─── reactive ────────────────────────────────────────────────────────────

    async def watch_invalidations(self) -> AsyncIterator[str]:
        while True:
            yield await self._invalidations.get()

    # ─── local-only helpers ──────────────────────────────────────────────────

    def sources_for(self, belief_id: str) -> list[str]:
        """Direct source parents of a belief, read off the graph rather than the
        belief document. Useful when checking the two agree."""
        return [
            p
            for p in self.graph.predecessors(belief_id)
            if self.graph.nodes[p].get("kind") == "source"
        ]

    def snapshot(self) -> dict[str, Any]:
        """Whole-store dump, for fixtures and debugging."""
        return {
            "sources": [s.to_mongo() for s in self.sources.values()],
            "beliefs": [b.to_mongo() for b in self.beliefs.values()],
            "provenance": [e.to_mongo() for e in self.edges.values()],
            "decisions": [d.to_mongo() for d in self.decisions.values()],
            "surgeries": [s.to_mongo() for s in self.surgeries.values()],
        }

    async def load_snapshot(self, payload: dict[str, Any]) -> None:
        await self.drop_all()
        for doc in payload.get("sources", []):
            await self.put_source(Source.from_mongo(doc))
        for doc in payload.get("beliefs", []):
            await self.put_belief(Belief.from_mongo(doc))
        for doc in payload.get("provenance", []):
            await self.put_edge(ProvenanceEdge.from_mongo(doc))
        for doc in payload.get("decisions", []):
            await self.put_decision(Decision.from_mongo(doc))
        for doc in payload.get("surgeries", []):
            await self.put_surgery(Surgery.from_mongo(doc))

    def assert_dag(self) -> None:
        """Provenance must stay acyclic or the blast radius never terminates.

        Cheap to check, and a cycle introduced by a careless ``derive()`` call is
        the kind of bug that only shows up as a hung demo.
        """
        if not nx.is_directed_acyclic_graph(self.graph):
            cycle = nx.find_cycle(self.graph)
            raise ValueError(f"provenance graph has a cycle: {cycle}")

    def edge_type_between(self, parent_id: str, child_id: str) -> EdgeType | None:
        data = self.graph.get_edge_data(parent_id, child_id)
        return data.get("edge_type") if data else None
