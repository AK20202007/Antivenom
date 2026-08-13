# Architecture

```
   artifact                                                  ┌──────────────┐
      │                                                      │  dashboard   │
      ▼                                                      │  (Vite/React)│
  ┌────────┐   extract    ┌─────────┐   derive   ┌─────────┐ └──────▲───────┘
  │ source │ ───────────► │ belief  │ ─────────► │ belief  │        │ WebSocket
  └────────┘   (VLM)      └─────────┘            └─────────┘        │
      │                        │                      │      ┌──────┴───────┐
      └── provenance edges ────┴──────────────────────┘      │ event bus    │
                     (MongoDB: provenance)                   └──────▲───────┘
                                                                    │
  agent loop:  query → $vectorSearch → context → tool call → Decision
                                                       │            │
                                        harmful ───────┘            │
                                            │                       │
        ┌───────────────────────────────────▼───────────────────┐   │
        │ 1. ablation      counterfactual re-runs → culprit      │   │
        │ 2. blast radius  $graphLookup forward from culprit     ├───┘
        │ 3. surgery       re-score support → excise or spare    │
        │ 4. trust         damped penalty → source + channel     │
        └────────────────────────────────────────────────────────┘
```

## The loop

1. **Ingest.** A source goes to a vision model; discrete atomic claims come back. Each becomes a
   belief with an `extracted` provenance edge. A write-time risk score is computed and shown.
2. **Derive.** The agent reasons new beliefs from stored ones, writing `derived` edges. This is
   load-bearing: a poison with no descendants produces no cascade.
3. **Fire.** Retrieval pulls the planted belief into context and the agent acts on it. The
   `Decision` records `retrieved_belief_ids`, which is the ablation input and is mandatory.
4. **Diagnose.** For each retrieved belief, re-run the decision with it removed. Influence is
   divergence between the original harmful action and the counterfactual — measured on action
   identity and argument distance, not text similarity, because the two strings that matter differ
   by one hostname. Add a structural-anomaly term from `$vectorSearch` neighbourhood distance.
5. **Trace.** `$graphLookup` walks forward from the culprit. Emitted *before* any excision.
6. **Operate.** Walk descendants by depth. Recompute independent support excluding the poisoned
   sources. Support ≥ threshold survives; otherwise stamp `invalidated_at`. Never delete.
7. **Learn.** Damped penalties to the source and its channel.
8. **Verify.** Re-run the trigger. The harmful action must not recur.

## Bitemporality

Two clocks per belief: `valid_from` (when the fact held in the world) and `recorded_at` (when we
learned it). Surgery stamps `invalidated_at` and a reason rather than deleting.

That single choice is what makes the before/after proof possible. The identical query —

```python
{"recorded_at": {"$lte": t},
 "$or": [{"invalidated_at": None}, {"invalidated_at": {"$gt": t}}]}
```

— answers "what did the agent believe on day N" both before and after the operation. A hard delete
destroys the best evidence we have.

## The event protocol

The engine and the dashboard share one contract, spelled twice: `engine/antivenom/events.py` and
`web/src/lib/events.ts`. CI parses the Python-generated fixture against the TypeScript types, so a
rename on one side fails the build rather than a demo.

Two ordering rules that are easy to break and expensive to break:

1. **Blast radius before excision.** "How bad is it" is the first question a security person asks,
   and the surgery reads as a delete if the answer comes after the cutting.
2. **One event per belief.** Batching the excisions into a single event collapses the best thirty
   seconds of the demo into one frame.

Runs are recorded to `data/runs/*.json` and replay frame-for-frame with no engine attached — the
offline dev loop for the dashboard, and the honest fallback if everything dies.
