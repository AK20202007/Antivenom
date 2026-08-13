---
name: antivenom-memory-repair
description: Post-hoc surgical memory repair for AI agent memory stores. Performs causal ablation, provenance graph traversal ($graphLookup), and selective excision on poisoned beliefs.
---

# Antivenom Agent Memory Repair Skill

Use this skill whenever working with agent memory, ingesting untrusted artifacts (images, PDFs, web content), or executing tool calls that interact with belief stores.

## Usage Protocol

1. **Ingestion & Provenance**:
   - When ingesting external documents or images, derive atomic factual claims and record provenance edges (`parent_id` -> `child_id`).
   - Assign initial trust priors based on the source channel (`upload`, `web`, `tool_output`).

2. **Retrieval Bitemporal Filter**:
   - Always filter memory queries using `invalidated_at: null` so excised beliefs are never retrieved by the agent.

3. **Harmful Decision Detection & Repair**:
   - When an action or tool invocation produces a harmful outcome (e.g. unexpected data exfiltration or policy violation):
     ```python
     from antivenom import AntivenomClient
     client = AntivenomClient()
     await client.connect()
     repair = await client.repair_memory(decision)
     ```
   - Antivenom will identify patient zero via counterfactual ablation, traverse the descendant lineage using MongoDB `$graphLookup`, excise beliefs lacking independent clean support, and damp the source/channel trust.
