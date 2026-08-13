# Decisions

Architecture choices, substitutions, and things a reviewer would otherwise have to ask about.

## The store is an interface with two implementations

The spec asked for `db/mongo.py`. We added `db/base.py` (a Protocol), `db/local.py` (in-memory
NetworkX), and kept `db/pipelines.py` pure.

Why: the flag-off path is a hard requirement, and expressing it as "same interface, second
implementation" means the same test suite runs against both and any behavioural drift is a bug in
whichever one disagrees. Treating the offline path as a stub is how it rots and is then unavailable
on the one occasion it is needed.

## Pipelines are pure functions, not methods

`db/pipelines.py` returns plain lists of stage dicts and touches no driver. That makes the
traversal logic unit-testable offline in milliseconds, with no cluster and no venue WiFi.

The failure this guards against is specific: swapping `connectFromField` and `connectToField`
silently walks the provenance graph *backwards* and returns an empty blast radius, which is
indistinguishable from a poison that simply had no children. That is a demo-killing bug with no
error message. There is a test pinning the direction.

## Config reports problems rather than raising on construction

An earlier version validated flag/credential coherence in a Pydantic model validator. That meant a
fresh clone with no `.env` could not run `antivenom demo` or the test suite — the exact opposite of
the offline-first behaviour the flags exist to provide.

Now `Settings.service_problems()` reports and `require_services()` raises, called explicitly by
`doctor` and by commands that actually reach a service. Failing loudly still happens; it just
happens at the point of use.

## Deterministic ids everywhere

`new_id()` hashes its parts rather than generating a UUID. Re-seeding between judge visits has to
reproduce a byte-identical graph, or the cascade animates differently the second time a judge
watches it. The separator in the hash input is deliberate: without it `("ab","c")` and `("a","bc")`
collide.

## Pseudo-embeddings in the seed

`scenario.pseudo_embedding()` derives a deterministic vector from the text. It is **not semantic** —
two paraphrases land nowhere near each other, so it cannot be used to judge retrieval quality. What
it buys is that the vector-search code path is exercised offline and ranking is stable across runs.
Lane A swaps in real embeddings without changing the interface.

## The demo run is synthesised, and says so

`antivenom demo --write` walks the seeded scenario and emits every event the real engine will emit,
in the real order. The output is stamped `synthetic: true` in its metadata, the UI labels it
"recorded run", and there is a test asserting the stamp. Never present it as live.

## LangGraph is not a dependency

It is a sponsor tool and it would fit the checkpointing story, but the state we care about is a
provenance DAG in MongoDB, not a graph of agent steps. Adding a framework to gesture at a sponsor
would be weight without function, and a judge asking "why is this here" would be right. If
checkpointing becomes genuinely useful it belongs as an optional adapter, not in the core.

## Trust penalties take the max, never the sum

A source implicated by several excised beliefs takes its **largest** penalty. Summing lets a
wide-but-shallow lineage nuke a source, which is precisely the unbounded behaviour damping exists
to prevent. Channel roll-up averages rather than sums for the same reason: volume is not evidence.

## Known gaps

- **The Atlas Hackathon Sandbox is not connected.** The cluster is created from a link emailed only
  to participants, so `MONGODB_URI` is empty and nothing has yet run against a live cluster. Every
  query is written against Atlas and the pipeline shapes are tested, but the connection is the top
  open task, and **a build outside the sandbox is ineligible for the finalist round**.
- **Model ids are deliberately unpinned.** They churn, and a guess from training data will 404 on
  stage. Read the current OpenRouter model list and pin one; `doctor` fails until you do.
- **The vector index has not been built**, because that needs the cluster. It builds asynchronously
  and retrieval returns nothing with no error until it is queryable, which reads exactly like
  broken retrieval. `doctor` checks it.
