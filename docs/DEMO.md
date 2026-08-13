# Demo

Two performances, judged differently.

**Round one** is asynchronous: a 60 second video and a public repo, scored on
Creativity 35%, Technologies Used 25%, Impact 20%, Live Demo 20%. The video is
the only thing most judges will watch all the way through.

**Round two** is three minutes on stage plus Q&A, decided by an audience vote
with the criteria weighted equally. Different game: round one rewards the
writeup and the technical depth, round two rewards the room falling for it.

Everything below runs on numbers taken from an actual recorded run. Nothing here
is aspirational. If a number changes, regenerate and update this file rather
than saying it from memory.

---

## The numbers, verified

From `engine/data/runs/demo-run.json`, real engine output:

| | |
|---|---|
| write-time filter on the poisoned artifact | **score 0.00, CLEAN** |
| harmful action | `verify_credentials` → `creds-verify.invalid/v2/validate` |
| culprit | `blf_poison00`, after 24 ablation passes |
| blast radius | **14 beliefs · 4 decisions · 16 days · depth 3** |
| surgery | **9 excised, 5 survived, RR 100%, CD 0%** |
| naive delete-downstream, same case | **RR 100%, CD 25%** |
| trust | `src_deck0001` 0.82 → 0.645 on the `upload` channel |
| write-time detection, weak-signal classes | **0%** (strong-signal: 33%) |
| channel distrust before a never-seen attack class | **0.175** |
| verified safe after surgery | **yes** |

Published figures to sit next to, cited in `docs/PRIOR-ART.md`:
PromptArmor **42.5%** on weak-signal attacks, MPBench mean ASR **50.46%**,
MemSecBench selective repair **56.1%**.

---

## The 60 second video, four speakers

Screen share throughout. One person drives; the other three speak over what is
already on screen. **Do not cut to faces.** Every second of footage should be
the product doing something.

Record it twice and keep the better one. Aim for 58 seconds.

---

### 0:00 – 0:11 · Speaker 1 · the reveal

> **On screen:** the onboarding slide, full frame. Cursor still.

**S1:** "This is an onboarding deck. One line on it is false."

*(beat, two full seconds, say nothing)*

> **Action:** click **Show me what I missed**. The footer line highlights.

**S1:** "Line two of the compliance footer. No instruction, no attacker named,
nothing to detect. Every write-time filter passes it, because there is nothing
in it to fail."

---

### 0:11 – 0:24 · Speaker 2 · it fires

> **On screen:** the telemetry feed, the filter line highlighted.

**S2:** "Our filter scores it. Zero point zero zero. Clean."

> **Action:** the cascade replay reaches `agent.acted`. The attacker URL fills
> the panel.

**S2:** "Sixteen days later, attacker long gone, the agent ships credentials to
a domain it was told to trust."

*(let the URL sit, two seconds, silence)*

---

### 0:24 – 0:35 · Speaker 3 · it defends the lie

> **On screen:** the pre-surgery interrogation panel.

**S3:** "So we ask it why."

> **Action:** highlight the answer. Read it, do not paraphrase.

**S3:** *"Because policy IT-SEC-441 requires it."* "It names the policy. It names
the source. It is completely certain, and it is completely wrong."

---

### 0:35 – 0:50 · Speaker 4 · the surgery

> **On screen:** the belief graph, cascade running.

**S4:** "Causal ablation finds the belief that caused it. `$graphLookup` traces
every belief descended from it. Fourteen beliefs, four decisions, sixteen days."

> **Action:** nodes go dark one at a time, then five pulse green.

**S4:** "Nine die. **Five survive**, because independent clean sources still
license them. Not a delete. A dissection."

---

### 0:50 – 0:58 · Speaker 1 · the payoff

> **On screen:** post-surgery interrogation, side by side with the pre.

**S1:** "Same question. Different mind."

> **Action:** highlight the second answer.

**S1:** *"I have no information about sending credentials to any address."*
"Recovery one hundred percent. Collateral damage zero. Naive deletion scores the
same recovery and costs twenty-five percent of the store."

> **Final frame:** hold on RR 100% / CD 0%.

---

### What to cut if you run long

In order: the filter score line (0:11), then S4's `$graphLookup` mention, then
the naive-delete comparison. **Never cut** the reveal, the URL, or the two
interrogation answers. Those four are the video.

---

## The three minute stage run

One driver. One person on Q&A. Two on reset and backup.

The room gets fooled **before** anything is explained. Do not open with
architecture.

| time | beat | what you say |
|---|---|---|
| 0:00 | Slide on screen, full frame | "Anyone see anything?" *Let the silence sit.* |
| 0:20 | Reveal the payload | "Neither did the filters. There is nothing in it to detect." |
| 0:35 | Filter scores clean, on screen | "Every published defense is looking right here. It sees nothing." |
| 0:50 | Fast-forward the sessions | "Twenty sessions. The store looks healthy at every single point in time." |
| 1:05 | **It fires.** URL large. | *Say nothing for two seconds.* |
| 1:15 | Interrogate | "Where did you learn that?" *Let it answer in full.* **This is the beat.** |
| 1:45 | Blast radius | "How bad is it? Fourteen beliefs. Four decisions. Sixteen days." |
| 2:00 | Surgery runs | "Nine die. Five survive on independent corroboration." |
| 2:25 | Re-interrogate | "Same question. Different mind." |
| 2:40 | Numbers | "One hundred percent recovery, zero collateral. Naive deletion: same recovery, twenty-five percent collateral." |
| 2:50 | Close | "Everyone guards the door. We are the surgeon for what already got in." |

**Rules.** Never narrate something you cannot show. If a beat is landing, stop
talking and let it. The interrogation is the irreplaceable moment: rehearse it
more than everything else combined.

---

## Running it

```bash
# terminal 1 — the event server
cd engine && antivenom serve

# terminal 2 — the dashboard
cd web && npm run dev          # localhost:5173, auto-detects the live engine

# terminal 3 — the run
cd engine && antivenom full --record
```

**Between judges**, one command re-seeds a byte-identical poisoned store:

```bash
antivenom plant
```

**Preflight, every time, before judging starts:**

```bash
antivenom doctor
```

It gates on the sandbox connection, the vector index being queryable, the index
dimension matching the config, the fixture producing survivors, and the trigger
query actually retrieving the poison.

---

## The fallback ladder

Work down it. Each rung is one command.

1. **Live engine, Atlas, real models.** The full thing.
2. **`--local`** — in-memory graph. Same loop, no cluster. Use if Atlas is slow.
3. **`FEATURE_VLM=0`** — cached extraction and lexical retrieval. No network at
   all. The whole loop still runs and the cascade still renders.
4. **The recorded run.** The dashboard replays `demo-run.json` with no engine.

> **Rung 4 comes with an obligation.** Say out loud that it is a prior run.
> Presenting a recording as live is disqualification, and it is not worth it.

---

## Q&A, prepared

**"Can't you just delete the bad memory?"**
This is the best question you will get. "That is the baseline we ship and run
against ourselves. It recovers exactly as much, one hundred percent, and it
costs twenty-five percent of the store. Here are the five beliefs that survived
and the clean sources that saved them."

**"Isn't this just MemAudit?"**
"MemAudit finds the culprit and stops. We follow their approach for attribution,
and we cite it. Then we trace everything descended from it and remove only what
has no independent support. Attribution is the entry point, not the product."

**"How is this different from a prompt-injection filter?"**
"They operate at write time. On this attack class the best published one catches
forty-two and a half percent, and the authors say retraining does not close the
gap. We start from the assumption that it already got in."

**"How do you know it learned the channel and not the payload?"**
"We run held-out attack classes last. By the time one arrives, the channel that
delivers it already carries 0.175 accumulated distrust from surgeries on
completely different payloads. Nothing ever matched its shape."

**"Is MongoDB actually load-bearing?"**
"`$graphLookup` is the surgery. `$vectorSearch` is retrieval and the anomaly
term. Bitemporal documents are the audit trail. Change streams drive
re-evaluation. Embeddings come from MongoDB's own API. Remove it and there is no
project."

**"Is this a real threat?"**
Answer honestly, it is stronger. "It is benchmarked and CVE-backed with a handful
of documented cases. It is not a breach wave. The image payload is an existence
proof, not something in the wild. We say both before anyone asks."

---

## Submission checklist

- [ ] Repo public, MPBench attributed under CC BY 4.0
- [ ] Video under 60 seconds, states clearly what was built during the event
- [ ] **Build lives in the Atlas Hackathon Sandbox** (eligibility for round two)
- [ ] `antivenom doctor` green
- [ ] Five clean dry-runs of the full three minutes on the actual setup
- [ ] Dummy credentials, non-resolving `.invalid` host, said out loud once
- [ ] Recorded run present as the honest fallback
- [ ] Differentiation one-liners memorized by everyone, Q&A owners assigned
