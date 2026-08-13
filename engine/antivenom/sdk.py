"""Antivenom SDK — Connect surgical memory repair to any custom LLM Agent."""

from __future__ import annotations

import asyncio
from typing import Any

from .config import settings
from .core.ablation import find_culprit
from .core.beliefs import ingest
from .core.provenance import blast_radius
from .core.surgery import operate
from .core.trust import propagate
from .db.mongo import MongoStore
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

    def __init__(self, uri: str | None = None, db_name: str = "antivenom"):
        self.uri = uri or settings().mongodb_uri
        self.db_name = db_name
        self.store = MongoStore(uri=self.uri, db_name=self.db_name)

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

    async def retrieve_context(
        self, query: str, limit: int = 5
    ) -> tuple[list[Belief], list[str]]:
        """Retrieve live (non-invalidated) beliefs for a prompt. Returns (beliefs, retrieved_belief_ids)."""
        live = await self.store.live_beliefs()
        selected = live[:limit]
        retrieved_ids = [b.id for b in selected]
        return selected, retrieved_ids

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
