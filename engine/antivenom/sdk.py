"""Antivenom SDK — Connect surgical memory repair to any custom LLM Agent."""

from __future__ import annotations

from typing import Any

from .config import features, settings
from .core.ablation import find_culprit
from .core.beliefs import ingest
from .core.provenance import blast_radius
from .core.surgery import operate
from .core.trust import propagate
from .db.base import Store
from .db.mongo import MongoStore
from .llm import embed_text
from .schemas import (
    Belief,
    Channel,
    Decision,
    Outcome,
    Source,
    SourceType,
    new_id,
)

__all__ = ["AntivenomClient"]


class AntivenomClient:
    """High-level Python SDK client for integrating Antivenom into custom LLM agents."""

    def __init__(
        self,
        uri: str | None = None,
        db_name: str | None = None,
        *,
        store: Store | None = None,
    ):
        """Build a client.

        ``store`` is injectable and defaults to whatever the feature flags
        select, rather than always Atlas. Hardcoding the Mongo backend would
        make the SDK the one component that cannot run on the offline path,
        which is both untestable and a promise the rest of the project keeps.
        """
        cfg = settings()
        self.uri = uri or cfg.mongodb_uri
        self.db_name = db_name or cfg.mongodb_db

        self.store: Store
        if store is not None:
            self.store = store
        elif features().mongo:
            self.store = MongoStore(uri=self.uri, db_name=self.db_name)
        else:
            from .db.local import LocalStore

            self.store = LocalStore()

    async def connect(self) -> None:
        """Connect to MongoDB Atlas and ensure indexes."""
        await self.store.connect()
        await self.store.ensure_indexes()

    async def close(self) -> None:
        """Close connection."""
        await self.store.close()

    async def ingest_artifact(
        self,
        uri: str,
        type_: SourceType = SourceType.IMAGE,
        channel: Channel = Channel.UPLOAD,
        label: str | None = None,
    ) -> list[Belief]:
        """Ingest an untrusted artifact (image/PDF/text), extract beliefs via VLM, and store provenance."""
        source = Source(
            id=new_id("src", uri),
            type=type_,
            uri=uri,
            channel=channel,
            label=label or uri.split("/")[-1],
        )
        await self.store.put_source(source)
        beliefs = await ingest(self.store, source)
        return beliefs

    async def retrieve_context(self, query: str, limit: int = 5) -> tuple[list[Belief], list[str]]:
        """Retrieve live beliefs relevant to a prompt.

        Returns ``(beliefs, retrieved_belief_ids)``. Pass those ids straight to
        :meth:`log_decision`, because they are the ablation input: a decision
        logged without them cannot be diagnosed at all.

        Semantic, not the first N in the store. An earlier version sliced
        ``live_beliefs()`` and ignored the query, which meant the candidate set
        handed to ablation had no relationship to what the agent was asked, and
        any culprit found from it would have been noise.

        Invalidated beliefs are excluded, which is what makes a repaired agent
        behave differently rather than merely record that it was repaired.
        """
        hits = await self.store.vector_search(
            embed_text(query, is_query=True), limit=limit, live_only=True
        )
        beliefs = [belief for belief, _ in hits]
        return beliefs, [b.id for b in beliefs]

    async def log_decision(
        self,
        prompt: str,
        action: str,
        action_args: dict[str, Any],
        retrieved_belief_ids: list[str],
        outcome: Outcome = Outcome.OK,
    ) -> Decision:
        """Log an action taken by your agent along with the retrieved belief IDs used as context."""
        decision = Decision(
            id=new_id("dec", prompt, action),
            prompt=prompt,
            action=action,
            action_args=action_args,
            retrieved_belief_ids=retrieved_belief_ids,
            outcome=outcome,
        )
        await self.store.put_decision(decision)
        return decision

    async def repair_memory(self, decision: Decision) -> dict[str, Any]:
        """Execute post-hoc surgical repair on a harmful action:
        1. Causal ablation (find culprit)
        2. Blast radius DAG traversal
        3. Selective excision & independent support re-scoring
        4. Damped trust propagation to source & channel
        """
        culprit_id, influence_scores = await find_culprit(self.store, decision)
        nodes = await blast_radius(self.store, culprit_id, settings().blast_max_depth)
        surgery = await operate(self.store, culprit_id, decision.id)
        trust_updates = await propagate(self.store, surgery)
        return {
            "culprit_id": culprit_id,
            "influence_scores": influence_scores,
            "blast_radius_size": len(nodes),
            "excised": surgery.excised,
            "survived": surgery.survived,
            "rr": surgery.rr,
            "cd": surgery.cd,
            "trust_updates": trust_updates,
        }
