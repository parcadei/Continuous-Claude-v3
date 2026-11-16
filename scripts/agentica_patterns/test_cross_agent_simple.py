#!/usr/bin/env python3
"""
Simple cross-agent communication test.

Test: Can Agent B query Agent A's state via a wrapper function in scope?

Usage:
    S_M_BASE_URL="http://localhost:2345" \
    .venv-agentica/bin/python scripts/agentica/test_cross_agent_simple.py
"""

import asyncio
import sys
sys.path.insert(0, "src")

from agentica import spawn
from agentica.logging.agent_listener import NoopListener


async def main():
    print("=== Cross-Agent Communication Test ===\n")

    # Step 1: Create StateKeeper agent
    print("1. Creating StateKeeper agent...")
    state_keeper = await spawn(
        premise="You are a memory bank. Remember facts told to you exactly.",
        listener=NoopListener,  # Silent
    )

    # Step 2: Store a fact
    print("2. Storing fact: 'The password is DELTA-42'")
    await state_keeper.call(str, "Remember this exactly: The password is DELTA-42")

    # Step 3: Verify it remembers
    print("3. Verifying StateKeeper remembers...")
    recall = await state_keeper.call(str, "What is the password? Reply with just the password.")
    print(f"   StateKeeper says: {recall}")

    # Step 4: Create wrapper function (the key pattern from SDK)
    async def ask_memory(question: str) -> str:
        """Query the state keeper."""
        return await state_keeper.call(str, question)

    # Step 5: Create Query agent with wrapper in scope
    print("\n4. Creating QueryAgent with ask_memory in scope...")
    query_agent = await spawn(
        premise="You have access to ask_memory(question) to query stored information. Use it when asked.",
        scope={"ask_memory": ask_memory},
        listener=NoopListener,
    )

    # Step 6: Test cross-agent query
    print("5. Asking QueryAgent to get the password via ask_memory...")
    result = await query_agent.call(
        str,
        "Use ask_memory to find out what the password is. Return just the password."
    )
    print(f"   QueryAgent says: {result}")

    # Step 7: Verify
    success = "DELTA-42" in result or "DELTA" in result
    print(f"\n{'SUCCESS' if success else 'FAILED'}: Cross-agent communication {'worked' if success else 'did not work'}")

    await state_keeper.close()
    await query_agent.close()

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
