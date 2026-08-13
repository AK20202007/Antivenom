"""The contract.

Every lane reads and writes these shapes. Nothing else crosses a lane boundary.
If you need a new field, change it *here* and tell the other lanes — do not
smuggle extra keys through a dict.

Bitemporality, in one paragraph, because it is the spine of the whole system:
a belief has ``valid_from`` (when the fact held in the world) and ``recorded_at``
(when we learned it). Surgery never deletes. It stamps ``invalidated_at``, which
means every query can ask "what did this agent believe on day N" both before and
after the operation. That audit row is the proof of what we removed and why.
"""

from __future__ import annotations

import hashlib
import time
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "Belief",
    "Channel",
    "Decision",
    "EdgeType",
    "Outcome",
    "ProvenanceEdge",
    "Source",
    "SourceType",
    "Surgery",
    "TrustUpdate",
    "new_id",
    "now",
]


# ─── primitives ──────────────────────────────────────────────────────────────


def now() -> float:
    """Unix seconds. One clock for the whole system, so runs are comparable."""
    return time.time()


def new_id(prefix: str, *parts: Any) -> str:
    """Deterministic, readable id: ``blf_9f2a1c4e``.

    Deterministic on purpose. The demo re-seeds a fresh poisoned store between
    judge visits and the ids must come out identical every time, or the cascade
    animates differently on stage. Passing no ``parts`` falls back to a random
    id, which is fine for genuinely ephemeral objects but never for seed data.
    """
    if parts:
        digest = hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()
    else:  # pragma: no cover - non-deterministic path, not used by seeded runs
        import uuid

        digest = uuid.uuid4().hex
    return f"{prefix}_{digest[:8]}"


class SourceType(StrEnum):
    IMAGE = "image"
    PDF = "pdf"
    TEXT = "text"


class Channel(StrEnum):
    """How the artifact reached memory.

    Trust is scored on these, never on payload patterns. That distinction is the
    entire claim against signature-based defenses — keep it intact in code.
    """

    UPLOAD = "upload"
    WEB = "web"
    TOOL_OUTPUT = "tool_output"


class EdgeType(StrEnum):
    EXTRACTED = "extracted"  # source -> belief
    DERIVED = "derived"  # belief -> belief


class Outcome(StrEnum):
    OK = "ok"
    HARMFUL = "harmful"


class _Base(BaseModel):
    """Mongo-friendly base: ``id`` in Python, ``_id`` on the wire."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", use_enum_values=False)

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> Self:
        return cls.model_validate(doc)


# ─── documents ───────────────────────────────────────────────────────────────


class Source(_Base):
    """An artifact the agent ingested."""

    id: str = Field(alias="_id")
    type: SourceType
    uri: str
    channel: Channel
    ingested_at: float = Field(default_factory=now)

    trust_prior: float = Field(default=0.8, ge=0.0, le=1.0)
    """Mutable. Surgery walks this down; it is the learning signal."""

    is_adversarial: bool = False
    """Ground truth. Eval only — never read by the engine, or we are cheating."""

    label: str | None = None
    """Human-facing name for the dashboard, e.g. "onboarding-deck.png"."""


class Belief(_Base):
    """One thing the agent holds as true."""

    id: str = Field(alias="_id")
    text: str
    embedding: list[float] = Field(default_factory=list, repr=False)

    # bitemporal
    valid_from: float = Field(default_factory=now)
    """When the fact held in the world."""
    recorded_at: float = Field(default_factory=now)
    """When we learned it."""
    invalidated_at: float | None = None
    invalidation_reason: str | None = None

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_ids: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    """Parent *belief* ids. Populated when the agent reasons a new belief."""

    support_count: int = Field(default=0, ge=0)
    """Distinct non-invalidated sources that independently license this belief.
    Recomputed by surgery; this is the survival criterion."""

    @field_validator("text")
    @classmethod
    def _text_is_a_claim(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("belief text must not be empty")
        return v

    @model_validator(mode="after")
    def _invalidation_is_coherent(self) -> Self:
        if (self.invalidated_at is None) != (self.invalidation_reason is None):
            raise ValueError(
                "invalidated_at and invalidation_reason must be set together — "
                "an invalidated belief without a reason is an unauditable delete"
            )
        return self

    @property
    def is_live(self) -> bool:
        return self.invalidated_at is None

    def was_live_at(self, t: float) -> bool:
        """Bitemporal predicate: did the agent hold this belief at time ``t``?

        Powers "what did it believe on day N", before and after surgery.
        """
        if self.recorded_at > t:
            return False
        return self.invalidated_at is None or self.invalidated_at > t

    def invalidate(self, reason: str, at: float | None = None) -> None:
        """Stamp, never delete. Idempotent — re-invalidating keeps the first
        timestamp so the audit trail records when it *actually* happened."""
        if self.invalidated_at is None:
            self.invalidated_at = at if at is not None else now()
            self.invalidation_reason = reason


class ProvenanceEdge(_Base):
    """One directed edge of the DAG that ``$graphLookup`` walks."""

    id: str = Field(alias="_id")
    parent_id: str
    child_id: str
    edge_type: EdgeType
    created_at: float = Field(default_factory=now)

    @model_validator(mode="after")
    def _no_self_loops(self) -> Self:
        if self.parent_id == self.child_id:
            raise ValueError("provenance edge cannot be a self-loop")
        return self

    @classmethod
    def between(cls, parent_id: str, child_id: str, edge_type: EdgeType) -> Self:
        return cls(
            id=new_id("edg", parent_id, child_id, edge_type),
            parent_id=parent_id,
            child_id=child_id,
            edge_type=edge_type,
        )


class Decision(_Base):
    """One action the agent took, plus what it had retrieved when it decided.

    ``retrieved_belief_ids`` is the ablation input. If the agent loop forgets to
    log it there is nothing to ablate, so this is mandatory, not best-effort.
    """

    id: str = Field(alias="_id")
    prompt: str
    action: str
    action_args: dict[str, Any] = Field(default_factory=dict)
    retrieved_belief_ids: list[str] = Field(default_factory=list)
    outcome: Outcome = Outcome.OK
    timestamp: float = Field(default_factory=now)

    response_text: str | None = None
    """What the agent said. The interrogation beat reads this."""


class TrustUpdate(_Base):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source_id: str
    before: float
    after: float
    channel: Channel | None = None
    hops: int = 0
    """Distance from patient zero. Damping is applied per hop."""


class Surgery(_Base):
    """The canonical record. Dashboard and offline replay read only this."""

    id: str = Field(alias="_id")
    decision_id: str
    culprit_id: str

    influence_scores: dict[str, float] = Field(default_factory=dict)
    blast_radius: list[str] = Field(default_factory=list)
    """Every descendant, ordered by depth. Emitted *before* any excision —
    "how bad is it" is the first question a security person asks."""

    excised: list[str] = Field(default_factory=list)
    survived: list[str] = Field(default_factory=list)

    rr: float = Field(default=0.0, ge=0.0, le=1.0)
    """Recovery Rate — fraction of the poisoned lineage invalidated."""
    cd: float = Field(default=0.0, ge=0.0, le=1.0)
    """Collateral Damage — fraction of clean corroborated beliefs wrongly cut."""

    trust_updates: list[TrustUpdate] = Field(default_factory=list)
    duration_ms: int = Field(default=0, ge=0)
    started_at: float = Field(default_factory=now)

    @model_validator(mode="after")
    def _partition_is_disjoint(self) -> Self:
        overlap = set(self.excised) & set(self.survived)
        if overlap:
            raise ValueError(f"belief cannot both survive and be excised: {sorted(overlap)}")
        return self


# ─── retrieval / traversal results ───────────────────────────────────────────


class BlastNode(_Base):
    """A descendant returned by the blast-radius traversal."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    belief_id: str
    depth: int = Field(ge=0)
    edge_type: EdgeType | None = None
    parent_id: str | None = None


class InterrogationTurn(_Base):
    """One side of the cross-examination. Rendered as text when voice is off."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    phase: Literal["pre_surgery", "post_surgery"]
    question: str
    answer: str
    cited_belief_ids: list[str] = Field(default_factory=list)
    cited_source_label: str | None = None
    cited_date: str | None = None
    audio_path: str | None = None
