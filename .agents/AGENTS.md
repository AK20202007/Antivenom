# Agent Rules — Antivenom Memory Protection

1. **Memory Safety & Provenance**:
   - Whenever this agent processes untrusted inputs (web pages, user uploads, external tool outputs), log discrete claims with provenance tracking.

2. **Bitemporal Filtering**:
   - Never query or suggest memory items where `invalidated_at != null`.

3. **Post-Hoc Surgical Repair**:
   - If a tool invocation or decision fails policy or produces an unsafe outcome, trigger `AntivenomClient.repair_memory()` to perform causal ablation, trace the blast radius via MongoDB `$graphLookup`, and prune poisoned belief lineages without nuking clean corroborated memory.
