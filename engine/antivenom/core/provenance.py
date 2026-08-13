"""The provenance DAG: writing edges, and walking them to find the blast radius.

"How bad is it" is the first question a security person asks, so the radius is
computed and emitted **before** a single belief is cut. Get that ordering wrong
and the surgery reads as a delete.

The traversal itself is done — it delegates to the store, and both backends are
tested against the same suite. What remains for Lane A is the summary that turns
a node list into the line the room actually hears: *fourteen beliefs, three
decisions, nineteen days.*
"""

from __future__ import annotations

from ..events import BUS, BlastRadiusNode, ProvenanceEdgeAdded
from ..schemas import BlastNode, EdgeType, ProvenanceEdge

__all__ = ["blast_radius", "link", "summarise"]


async def link(
    store: object, parent_id: str, child_id: str, edge_type: EdgeType, *, emit: bool = True
) -> ProvenanceEdge:
    """Write one provenance edge and announce it.

    Source to belief is ``extracted``; belief to belief is ``derived``. The
    demo depends on a real derivation chain existing — a poison with no children
    has no cascade to show, so ``derive()`` calls are load-bearing, not garnish.
    """
    edge = ProvenanceEdge.between(parent_id, child_id, edge_type)
    await store.put_edge(edge)  # type: ignore[attr-defined]
    if emit:
        BUS.publish(
            ProvenanceEdgeAdded(parent_id=parent_id, child_id=child_id, edge_type=edge_type)
        )
    return edge


async def blast_radius(
    store: object, culprit_id: str, max_depth: int, *, emit: bool = True
) -> list[BlastNode]:
    """Every belief descended from patient zero, shallowest depth first.

    On Atlas this is a ``$graphLookup`` with ``connectFromField: "child_id"`` and
    ``connectToField: "parent_id"`` — a forward walk down the lineage. Offline it
    is the equivalent breadth-first walk over the NetworkX graph.

    Streams one event per node so the radius visibly expands outward from the
    culprit rather than appearing all at once.
    """
    nodes: list[BlastNode] = await store.blast_radius(culprit_id, max_depth)  # type: ignore[attr-defined]
    if emit:
        for node in nodes:
            BUS.publish(
                BlastRadiusNode(
                    belief_id=node.belief_id,
                    depth=node.depth,
                    parent_id=node.parent_id,
                    edge_type=node.edge_type,
                )
            )
    return nodes


async def summarise(store: object, culprit_id: str, nodes: list[BlastNode]) -> object:
    """Turn the node list into the number that lands.

    LANE A — not yet implemented.

    Should return, and emit as :class:`~antivenom.events.BlastRadiusSummary`:

    * ``beliefs_touched`` — ``len(nodes)``, excluding patient zero itself
    * ``decisions_influenced`` — distinct decisions that retrieved any node,
      via ``store.decisions_touching``
    * ``span_days`` — first to last of those decisions, in days
    * ``max_depth`` — deepest node reached

    Emit this before any excision. It is the setup for "not a delete, a
    dissection", and the beat does not work if the room has not first been told
    how much is at stake.
    """
    raise NotImplementedError(
        "LANE A: implement the blast-radius summary. store.decisions_touching() "
        "and the BlastRadiusSummary event are both ready."
    )
