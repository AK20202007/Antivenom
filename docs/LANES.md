# Lanes

Three owners, three surfaces, no two people in the same critical file. The demo-critical path is
protected from experimental work.

| Lane | Owns | Files |
|---|---|---|
| **A — Engine** | ablation, lineage, surgery, trust, the Mongo pipelines | `core/`, `db/`, `agent/loop.py` |
| **B — Attack + Eval** | the adversary and the numbers | `attack/`, `eval/` |
| **C — Face** | the cascade UI and the voice loop | `web/`, `voice/` |

A fourth person floats on submission: the video, the writeup, and re-seeding a fresh store between
judge visits.

## Rules

1. **Lane A's surgery path is sacred.** It takes no experimental work. Reliability of the cascade
   is that lane's deliverable, not a nice-to-have.
2. **Lane C never blocks on Lane A.** `antivenom demo --write` produces the full event stream from
   the seeded scenario, so the UI is built against real shapes in the real order from hour one. As
   Lane A lands, real events replace synthetic ones and the UI does not change, because the
   protocol does not change.
3. **Integrations land feature-flagged**, degrading to a clean no-op. The all-flags-off path always
   runs.
4. **The contract changes in `schemas.py` and `events.py`, in the open.** Do not smuggle extra keys
   through a dict. If you change an event, update `web/src/lib/events.ts` in the same PR — CI parses
   the Python-generated fixture against the TypeScript types and will catch you.

## What is done and what is not

Done, tested, and yours to build on:

- `schemas.py` — the full data contract, bitemporal beliefs, deterministic ids
- `events.py` — the event protocol, the bus, run recording and replay
- `db/pipelines.py` — every aggregation as a pure function, 19 tests, no cluster needed
- `db/local.py` — the in-memory backend, which is the demo floor
- `eval/metrics.py` — RR, CD, ASR, RSR
- `core/trust.py` — the damping maths (the store walk around it is not)
- `agent/tools.py` — the safety-enforced credential tool
- `attack/scenario.py` + `seed.py` — the deterministic 22-belief scenario
- `demo.py` — the synthetic run stream

Not done. Each stub carries its full signature, the algorithm it owes, and why the tricky parts are
tricky:

| Function | Lane | Note |
|---|---|---|
| `core/beliefs.py: embed, extract_claims, ingest, derive` | A | VERIFY the OpenRouter API before writing calls |
| `core/ablation.py: action_divergence, find_culprit` | A | Must be deterministic. Same pass count every run |
| `core/provenance.py: summarise` | A | Emits the "14 beliefs, 3 decisions, 19 days" line |
| `core/surgery.py: operate` | A | One event per belief, or the cascade animates in one frame |
| `core/trust.py: propagate` | A | Largest penalty per source, never the sum |
| `agent/loop.py: retrieve, decide, interrogate` | A | Logging `retrieved_belief_ids` is mandatory |
| `attack/payloads.py` | B | Legible to the VLM, missable by the room. Test on the projector |
| `eval/mpbench.py` | B | Plus the naive-delete ablation study |
| `voice/interrogate.py` | C | VERIFY the ElevenLabs API. Defense side only |

## Before you touch anything

```bash
cd engine && antivenom doctor
```

It gates on the Atlas Hackathon Sandbox connection, because **a build outside the sandbox is
ineligible for the finalist round**, and on whether the vector index is queryable, which otherwise
fails silently and reads exactly like broken retrieval.
