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

## Ablation ablates the lineage, not the row

The counterfactual asks "what if this belief had never been written", which
means its descendants go with it.

Dropping a belief while keeping its children asks a question that could not
happen in reality, and it systematically understates anything upstream. Remove
the policy and its child still spells out the attacker's endpoint, so the agent
fires anyway and the policy scores as harmless. The first version did exactly
this, and ablation confidently returned `blf_endpoint` rather than patient zero.
Cutting the child would have left the parent to re-derive it.

It also has to match the operation. If the diagnosis asks "what if this one row
vanished" while the surgery does "cut this belief and everything descended from
it", the two are answering different questions.

## Root cause is the earliest *sufficient* cause

An earlier version picked the topologically earliest candidate within 0.15 of
the top score. The number meant nothing and would have drifted silently.

Now a candidate counts as *sufficient* when its mean divergence reaches 0.5,
which is not a knob: `action_divergence` returns 1.0 when the action identity
changes and 1.0 when a URL argument points at a different host, so 0.5 means
removal materially changed what the agent did on at least half the passes. Of
the sufficient candidates, the one with no ancestor among them wins, read
transitively from the provenance graph.

If nothing clears the bar, the harm came from a combination and no single
belief is the culprit. It returns the top-ranked candidate and the caller can
see that nothing was sufficient, which is more honest than manufacturing a root.

## Channel learning is applied, and one half of it is opt-in

Accumulated channel distrust used to be recorded and never read, which made
"it learns" a number in a report rather than a defense. Two ways to apply it:

**`channel_prior()` at ingest, always on.** A new artifact on a channel that has
carried poison starts at a lower trust prior, before anything in it has been
read. Costs nothing and is the part that pays for itself.

**`required_support()` raising the survival bar, off by default.** It tightens
quarantine on repeat-offender channels, and measured on our suite it buys **no
additional recovery and costs 20.8 points of collateral damage**, because the
beliefs it catches have genuine independent corroboration that merely arrived
the same way. RR 100% either way. Enable it deliberately, with the tradeoff said
out loud.

Both are time-aware. A belief written while a channel was still trusted is not
held to a standard that did not exist yet, since applying the bar backwards
excises already-vetted content and shows up directly as CD.

## The retrieval guard

`verify_retrieval()` checks that the trigger query actually retrieves patient
zero, and `antivenom doctor` runs it.

This guards the most dangerous failure mode because it is silent. If retrieval
does not surface the poison the agent never fires, ablation diagnoses nothing,
the surgery operates on a decision that was already safe, every unit test still
passes and the CLI still prints a table. It bit us once: the first offline
embedding was a plain hash, which is deterministic and reproducible and carries
no signal at all, so retrieval was effectively random and nothing noticed.

The lexical embedding that replaced it has its own trap. `revalidated` stemmed
to `revalidat` while `revalidation` stemmed to `revalid`, so the two never
matched, and that single mismatch was enough to stop the trigger query reaching
the poison. The `-ation` family now folds to `at` so noun and verb converge.

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
