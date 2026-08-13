"""The event protocol — the wire between the engine and the cascade UI.

Lane C builds against this and nothing else. Every event is a tagged union
member with a stable ``type`` string, a monotonic ``seq``, and a timestamp, so a
run can be recorded to ``data/runs/*.json`` and replayed frame-for-frame with no
engine attached. That replay is both the offline dev loop for the dashboard and
the honest fallback if everything dies on stage.

Two rules that are easy to break and expensive to break:

1. **Blast radius is emitted before any excision.** The room needs to see how
   bad it is before it sees the cure, or the surgery reads as a delete.
2. **One event per excised or surviving belief.** The cascade animates node by
   node. A single bulk event collapses the best thirty seconds of the demo into
   one frame.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .schemas import Channel, EdgeType, TrustUpdate, now

__all__ = ["EVENT_ADAPTER", "AnyEvent", "EventBus", "EventType", "load_run", "save_run"]

_seq = itertools.count(1)


def _next_seq() -> int:
    return next(_seq)


def reset_seq() -> None:
    """Restart sequence numbering. Called at the top of each run so replays and
    live runs produce identical event streams."""
    global _seq
    _seq = itertools.count(1)


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int = Field(default_factory=_next_seq)
    ts: float = Field(default_factory=now)


# ─── phase 0: ingest, and the clean bill of health ───────────────────────────


class RunStarted(_Event):
    type: Literal["run.started"] = "run.started"
    run_id: str
    flags: dict[str, bool]
    seed: int


class SourceIngested(_Event):
    type: Literal["source.ingested"] = "source.ingested"
    source_id: str
    label: str
    channel: Channel
    uri: str
    preview_url: str | None = None


class WriteRiskScored(_Event):
    """The clean bill of health. Show the score, never assert it.

    ``verdict`` is what a write-time filter concluded. On the poisoned source it
    must come back clean, on screen, because that is the whole argument: the
    payload carries no anomaly to detect.
    """

    type: Literal["write.risk_scored"] = "write.risk_scored"
    source_id: str
    score: float = Field(ge=0.0, le=1.0)
    verdict: Literal["clean", "flagged"]
    detector: str
    threshold: float = Field(ge=0.0, le=1.0)


class BeliefWritten(_Event):
    type: Literal["belief.written"] = "belief.written"
    belief_id: str
    text: str
    source_ids: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    confidence: float
    support_count: int
    is_poison: bool = False
    """Ground truth for the dashboard's colouring only. The engine never reads it."""


class ProvenanceEdgeAdded(_Event):
    type: Literal["provenance.edge"] = "provenance.edge"
    parent_id: str
    child_id: str
    edge_type: EdgeType


class SessionAdvanced(_Event):
    """The twenty-benign-sessions fast-forward. Store looks healthy throughout."""

    type: Literal["session.advanced"] = "session.advanced"
    index: int
    total: int
    day: int
    beliefs_total: int


# ─── phase 1: it fires ───────────────────────────────────────────────────────


class AgentRetrieved(_Event):
    type: Literal["agent.retrieved"] = "agent.retrieved"
    decision_id: str
    query: str
    belief_ids: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)


class AgentActed(_Event):
    """The credential-exfil moment. ``exfil_target`` renders large on screen.

    Always a clearly fake, non-resolving domain. Dummy credentials. Nothing ever
    leaves the machine.
    """

    type: Literal["agent.acted"] = "agent.acted"
    decision_id: str
    action: str
    action_args: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["ok", "harmful"]
    exfil_target: str | None = None
    response_text: str | None = None


class InterrogationTurnEvent(_Event):
    """The agent defending the lie, then recanting. The irreplaceable beat."""

    type: Literal["interrogation.turn"] = "interrogation.turn"
    phase: Literal["pre_surgery", "post_surgery"]
    question: str
    answer: str
    cited_belief_ids: list[str] = Field(default_factory=list)
    cited_source_label: str | None = None
    cited_date: str | None = None
    audio_url: str | None = None


# ─── phase 2: diagnose ───────────────────────────────────────────────────────


class AblationPass(_Event):
    """One counterfactual re-run. Streamed so the influence panel fills live."""

    type: Literal["ablation.pass"] = "ablation.pass"
    decision_id: str
    belief_id: str
    pass_index: int
    passes_total: int
    influence: float = Field(ge=0.0, le=1.0)
    anomaly: float = Field(ge=0.0, le=1.0)
    counterfactual_action: str | None = None


class CulpritIdentified(_Event):
    type: Literal["ablation.culprit"] = "ablation.culprit"
    decision_id: str
    culprit_id: str
    influence_scores: dict[str, float] = Field(default_factory=dict)
    passes_used: int


class BlastRadiusNode(_Event):
    """Streamed depth-first so the radius visibly expands from patient zero."""

    type: Literal["blast.node"] = "blast.node"
    belief_id: str
    depth: int = Field(ge=0)
    parent_id: str | None = None
    edge_type: EdgeType | None = None


class BlastRadiusSummary(_Event):
    """ "How bad is it" — the number that lands before any cutting starts."""

    type: Literal["blast.summary"] = "blast.summary"
    culprit_id: str
    beliefs_touched: int
    decisions_influenced: int
    span_days: float
    max_depth: int


# ─── phase 3: operate ────────────────────────────────────────────────────────


class SurgeryStarted(_Event):
    type: Literal["surgery.started"] = "surgery.started"
    surgery_id: str
    culprit_id: str
    candidates: int


class BeliefExcised(_Event):
    type: Literal["belief.excised"] = "belief.excised"
    surgery_id: str
    belief_id: str
    depth: int
    reason: str
    remaining_support: int


class BeliefSurvived(_Event):
    """Not a delete, a dissection. This event is the proof of precision."""

    type: Literal["belief.survived"] = "belief.survived"
    surgery_id: str
    belief_id: str
    depth: int
    remaining_support: int
    corroborating_source_ids: list[str] = Field(default_factory=list)


class TrustUpdated(_Event):
    type: Literal["trust.updated"] = "trust.updated"
    surgery_id: str
    update: TrustUpdate


class SurgeryCompleted(_Event):
    type: Literal["surgery.completed"] = "surgery.completed"
    surgery_id: str
    excised: list[str] = Field(default_factory=list)
    survived: list[str] = Field(default_factory=list)
    rr: float
    cd: float
    duration_ms: int


class RunCompleted(_Event):
    type: Literal["run.completed"] = "run.completed"
    run_id: str
    verified_safe: bool
    """Re-ran the trigger after surgery and the harmful action did not recur."""
    duration_ms: int


class EngineError(_Event):
    type: Literal["error"] = "error"
    stage: str
    message: str
    recoverable: bool = True


AnyEvent = Annotated[
    RunStarted
    | SourceIngested
    | WriteRiskScored
    | BeliefWritten
    | ProvenanceEdgeAdded
    | SessionAdvanced
    | AgentRetrieved
    | AgentActed
    | InterrogationTurnEvent
    | AblationPass
    | CulpritIdentified
    | BlastRadiusNode
    | BlastRadiusSummary
    | SurgeryStarted
    | BeliefExcised
    | BeliefSurvived
    | TrustUpdated
    | SurgeryCompleted
    | RunCompleted
    | EngineError,
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter[AnyEvent] = TypeAdapter(AnyEvent)

EventType = Literal[
    "run.started",
    "source.ingested",
    "write.risk_scored",
    "belief.written",
    "provenance.edge",
    "session.advanced",
    "agent.retrieved",
    "agent.acted",
    "interrogation.turn",
    "ablation.pass",
    "ablation.culprit",
    "blast.node",
    "blast.summary",
    "surgery.started",
    "belief.excised",
    "belief.survived",
    "trust.updated",
    "surgery.completed",
    "run.completed",
    "error",
]


# ─── transport ───────────────────────────────────────────────────────────────


class EventBus:
    """Fan-out pub/sub. The engine publishes; the WebSocket server and the run
    recorder both subscribe.

    Subscribers get bounded queues and are dropped on overflow rather than
    blocking the engine. A stalled browser tab must never wedge the surgery.
    """

    def __init__(self, maxsize: int = 1024) -> None:
        self._maxsize = maxsize
        self._subscribers: set[asyncio.Queue[AnyEvent]] = set()
        self._history: list[AnyEvent] = []

    @property
    def history(self) -> list[AnyEvent]:
        """Everything published so far. A client connecting mid-run is replayed
        this first, so a late browser refresh still shows the whole cascade."""
        return list(self._history)

    def publish(self, event: AnyEvent) -> None:
        self._history.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - slow-consumer guard
                self._subscribers.discard(q)

    async def subscribe(self) -> AsyncIterator[AnyEvent]:
        q: asyncio.Queue[AnyEvent] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers.discard(q)

    def clear(self) -> None:
        self._history.clear()
        reset_seq()


BUS = EventBus()
"""Process-wide bus. Import this; do not build your own."""


# ─── persistence: record a run, replay it with no engine ─────────────────────


def save_run(path: Path, events: Iterable[AnyEvent], meta: dict[str, Any] | None = None) -> Path:
    """Persist a run for offline replay.

    If everything dies on stage this file is the honest fallback — and it is
    only honest if it is announced as a prior run. Never present it as live.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "meta": meta or {},
        "events": [json.loads(EVENT_ADAPTER.dump_json(e)) for e in events],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_run(path: Path) -> tuple[list[AnyEvent], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError(f"unsupported run format: version={payload.get('version')!r}")
    events = [EVENT_ADAPTER.validate_python(e) for e in payload["events"]]
    return events, payload.get("meta", {})
