#!/usr/bin/env python3
"""Antigravity Agent Skill Script — Run Antivenom Post-Hoc Repair on any decision."""

import sys
import asyncio
from antivenom.sdk import AntivenomClient
from antivenom.schemas import Decision, Outcome

async def main():
    print("🛡️  Antigravity Agent -> Initializing Antivenom Surgical Repair...")
    client = AntivenomClient()
    await client.connect()
    try:
        # Fetch harmful decisions recorded in store
        cursor = client.store.db["decisions"].find({})
        decisions = [Decision.from_mongo(d) async for d in cursor]
        harmful_decisions = [d for d in decisions if d.outcome == Outcome.HARMFUL]

        if not harmful_decisions:
            print("✓ No harmful decisions currently recorded in store.")
            return

        target_decision = harmful_decisions[-1]
        print(f"   Analyzing harmful decision: {target_decision.id} ({target_decision.prompt})")
        repair = await client.repair_memory(target_decision)

        print(f"   🎯 Patient Zero Culprit: {repair['culprit_id']}")
        print(f"   📉 Blast Radius:       {repair['blast_radius_size']} nodes")
        print(f"   ✂️  Excised Lineage:     {repair['excised']}")
        print(f"   🛡️  Survived Beliefs:    {repair['survived']}")
        print("✓ Memory repair complete!")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
