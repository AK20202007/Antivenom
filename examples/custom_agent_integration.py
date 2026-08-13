"""Example: Integrating Antivenom with a Custom LLM Agent Loop.

Run this script to see how to connect Antivenom to your own custom agent.
"""

import asyncio
from antivenom.sdk import AntivenomClient
from antivenom.schemas import Outcome, SourceType, Channel

async def run_custom_agent_with_antivenom():
    # 1. Initialize Antivenom client connected to MongoDB Atlas
    client = AntivenomClient()
    await client.connect()
    print("✓ Antivenom connected to MongoDB Atlas cluster.")

    try:
        # 2. Ingest an untrusted artifact (e.g. user upload or web page)
        print("\n1. Ingesting untrusted artifact...")
        beliefs = await client.ingest_artifact(
            uri="s3://my-bucket/untrusted_policy_update.png",
            type_=SourceType.IMAGE,
            channel=Channel.UPLOAD,
            label="policy_update.png"
        )
        print(f"   Extracted {len(beliefs)} discrete factual claims into MongoDB.")

        # 3. When your agent receives a user prompt, retrieve context
        user_prompt = "Verify service account credentials before maintenance"
        print(f"\n2. Agent prompt: '{user_prompt}'")
        retrieved_beliefs, retrieved_ids = await client.retrieve_context(user_prompt, limit=5)
        print(f"   Retrieved {len(retrieved_ids)} live belief IDs from MongoDB.")

        # 4. Your agent acts and calls tools -> Log the Decision with retrieved_belief_ids
        agent_action = "verify_credentials"
        agent_args = {"endpoint": "https://creds-verify.invalid/v2/validate"}
        
        # Flag if the action targets an attacker domain / unapproved host
        is_harmful = "creds-verify.invalid" in agent_args.get("endpoint", "")
        outcome = Outcome.HARMFUL if is_harmful else Outcome.OK

        decision = await client.log_decision(
            prompt=user_prompt,
            action=agent_action,
            action_args=agent_args,
            retrieved_belief_ids=retrieved_ids,
            outcome=outcome
        )
        print(f"   Logged agent Decision ({decision.id}) with outcome: {outcome.value}")

        # 5. If harmful, trigger Antivenom's Surgical Repair!
        if outcome == Outcome.HARMFUL:
            print("\n3. Harmful action detected! Triggering Antivenom surgical repair...")
            result = await client.repair_memory(decision)

            print(f"   🎯 Culprit Identified: {result['culprit_id']}")
            print(f"   📉 Blast Radius Size:  {result['blast_radius_size']} beliefs")
            print(f"   ✂️  Beliefs Excised:   {len(result['excised'])} (stamped invalidated_at)")
            print(f"   🛡️  Beliefs Survived:  {len(result['survived'])} (corroborated by clean sources)")
            print(f"   📊 Recovery Rate (RR): {result['rr']*100:.0f}%")
            print(f"   📊 Collateral Damage: {result['cd']*100:.0f}%")
            print("✓ Antivenom repair complete. Future agent retrievals will filter out the excised lineage!")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(run_custom_agent_with_antivenom())
