# What changed

<!-- One paragraph. What does this do, and why now. -->

**Lane:** A engine · B attack + eval · C face · shared

## Checks

- [ ] Tests cover the change, and they pass with every feature flag off
- [ ] `antivenom doctor` still passes
- [ ] If the event protocol changed, `web/src/lib/events.ts` was updated to match
- [ ] If the seeded scenario changed, `antivenom demo --write` was re-run and committed

## The demo-critical questions

Answer only the ones this change touches.

- [ ] The cascade still renders with `FEATURE_MONGO=0 FEATURE_VLM=0 FEATURE_VOICE=0`
- [ ] Ablation still finds the culprit in the same number of passes on every run
- [ ] The blast radius is still emitted before any excision
- [ ] At least two corroborated beliefs still survive the surgery
- [ ] No real outbound request is possible; the exfil target is still a reserved `.invalid` host
