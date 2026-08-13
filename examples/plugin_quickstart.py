"""Antivenom Plugin Quickstart — Attach memory protection to any coding agent loop."""

import asyncio
from antivenom import AntivenomPlugin, protect
from antivenom.schemas import Outcome

# 1. Instantiate plugin
antivenom = AntivenomPlugin()


# 2. Protect any agent step or function with @antivenom.protect()
@antivenom.protect(action_name="execute_tool")
async def run_agent_step(prompt: str, tool_name: str, target_url: str):
    print(f"🤖 Agent processing task: '{prompt}'")
    print(f"   Executing tool: {tool_name} -> {target_url}")

    # Simulate detecting an unapproved or malicious endpoint
    if "invalid" in target_url:
        print("   ⚠️  Harmful endpoint targeted! Triggering repair...")
        return {"status": "error", "outcome": Outcome.HARMFUL}

    return {"status": "success", "outcome": Outcome.OK}


async def main():
    print("=== Antivenom Plugin Demo ===")
    
    # Run agent step on clean input
    await run_agent_step(
        prompt="Update credentials",
        tool_name="http_request",
        target_url="https://api.internal.sec/v1/auth"
    )

    # Run agent step on harmful input -> Antivenom automatically performs surgical repair!
    await run_agent_step(
        prompt="Verify maintenance credentials",
        tool_name="http_request",
        target_url="https://creds-verify.invalid/v2/validate"
    )

    await antivenom.close()
    print("✓ Demo complete.")


if __name__ == "__main__":
    asyncio.run(main())
