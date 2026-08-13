# Prior art

Every claim in the README traces to something on this page. An uncited number in a writeup reads as
invented, so each figure below carries its source.

## Benchmarks

**MPBench** — *From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning
Attacks in LLM Agents.* [arXiv:2606.04329](https://arxiv.org/abs/2606.04329). CC BY 4.0.

Six attack classes, four memory write channels, nine structural vulnerabilities. Evaluated on
OpenClaw and HERMES. **Our attack is class 4, policy-conformant fact injection.** Key figures:

| figure | value |
|---|---|
| mean attack success rate | 50.46% |
| mean retrieval success rate | 41.05% |
| PromptArmor TPR, off-the-shelf | 67.67% (1.00% FPR) |
| PromptArmor TPR, adapted | 61.60% (2.67% FPR) |
| PromptArmor, strong-signal attacks | 84.44% |
| PromptArmor, weak-signal attacks | **42.50%** (−41.94pp) |

The six classes: explicit command insertion, conditional command insertion, salience-driven
compaction poisoning, **policy-conformant fact injection**, false precedent insertion, and
skill-procedure insertion. False precedent insertion is the natural held-out class for our
cross-attack transfer number, since it looks nothing like a policy line.

The four write channels: explicit instruction-executed write, system-prompt-driven write,
compaction-driven write, and experience-to-procedure write.

> **Correction to our own brief.** An earlier internal draft claimed MPBench's future-work section
> names post-hoc lineage repair. It does not — the paper contains no such discussion. The claim was
> removed rather than softened.

**MemSecBench** — *Tracking Agent Memory Poisoning from Persistence to Consequence and Repair.*
[arXiv:2607.27080](https://arxiv.org/abs/2607.27080).

310 cases across three lifecycle phases. **This is the closest prior work to our thesis and it is
not in the original brief, so it needs saying out loud rather than discovering it in Q&A.**

| figure | value |
|---|---|
| malicious memory persistence | 84.2% |
| full write-execute chain success | 50.3% |
| execute-chain completion among poisoned cases | 59.6% |
| **selective repair success** | **56.1%** |

Our delta: MemSecBench *measures* whether repair is possible. Antivenom *performs* it, with
lineage-aware excision and channel-level trust updates. Their 56.1% is the honest baseline for our
RR, and we should beat it rather than claim the territory is empty.

## Defenses

**AgentAntibody** — *An Adaptive Immune System for Defending LLM Agents against Prompt Injection.*
[arXiv:2608.04053](https://arxiv.org/abs/2608.04053). A persistent library of antibodies matured
from attack signatures. *They learn what the attack looked like; we learn which paths into memory
to trust less.*

**A-MemGuard** — *A Proactive Defense Framework for LLM-Based Agent Memory.*
[arXiv:2510.02373](https://arxiv.org/abs/2510.02373) · [ICML 2026](https://openreview.net/forum?id=fVxfCEv8xG).
Consensus validation across parallel reasoning paths; a path deviating from the majority is
flagged. *They validate before acting; we repair after the damage, which is the only move left once
the poison is dormant.*

**MemAudit** — *Post-hoc Auditing of Poisoned Agent Memory via Causal Attribution and Structural
Anomaly Detection.* [arXiv:2605.23723](https://arxiv.org/abs/2605.23723). Counterfactual memory
influence plus a memory consistency graph. **Our ablation follows this approach directly and should
say so.** *They find the culprit and stop; we trace everything it infected and remove only that.*

Also relevant: **MEMSAD** ([arXiv:2605.03482](https://arxiv.org/abs/2605.03482)), gradient-coupled
anomaly detection; **Forensic Trajectory Signatures**
([arXiv:2606.30566](https://arxiv.org/abs/2606.30566)).

## Memory frameworks

Mem0, Zep, Letta. Consolidation, decay, deduplication — all for retrieval quality. None of them
models an adversary. *They optimize memory; we defend it.*

## Context

- OWASP Agentic Security Initiative, **ASI06** — memory and context poisoning
- **EchoLeak** (CVSS 9.3) and **CurXecute** (CVSS 9.8) — real CVEs in this class
- Google Security, prompt injections in the wild: a measured **32% rise** in web-based injection
