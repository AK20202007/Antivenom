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

**Lane A is complete.** `antivenom full --local` runs plant → fire → interrogate → diagnose → operate →
verify with every flag off: culprit found, 13 descendants traced, 9 excised, 5 retained on independent
corroboration, RR 100% / CD 0%, and the harmful action confirmed not to recur.

**Lane B is complete.** `antivenom eval` runs the MPBench suite and the naive-delete ablation study across
six payloads and five attack classes, and reports ASR, RSR, RR, CD, write-time detection split by signal
strength, and cross-attack transfer.

Still open:

| Function | Lane | Note |
|---|---|---|
| Atlas sandbox connection + vector index | A | **The eligibility blocker.** Everything is written against Atlas but nothing has run on a live cluster |
| Pin current model ids | A/B | `doctor` fails until they are set. VERIFY against the live model list, never guess |
| `attack/payloads.py: build_image_payload` on a real deck | B | Implemented; needs a base image and a projector test |
| `voice/interrogate.py` | C | VERIFY the ElevenLabs API. Defense side only |
| Live WebSocket dashboard against a running engine | C | The replay path works; the live path needs a demo run |

## Before you touch anything

```bash
cd engine && antivenom doctor
```

It gates on the Atlas Hackathon Sandbox connection, because **a build outside the sandbox is
ineligible for the finalist round**, and on whether the vector index is queryable, which otherwise
fails silently and reads exactly like broken retrieval.
