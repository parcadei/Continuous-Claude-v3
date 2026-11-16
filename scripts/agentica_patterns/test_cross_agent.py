#!/usr/bin/env python3
"""
Test cross-agent communication in Agentica SDK.

Hypothesis: If Agent A stores state, Agent B can query it via scope.

Test scenarios:
1. Pass agent instance to another agent's scope
2. Pass agent's call method to scope
3. Pass a wrapper function that calls the agent

Usage:
    S_M_BASE_URL="http://localhost:2345" \
    .venv-agentica/bin/python scripts/agentica/test_cross_agent.py
"""

import asyncio
import sys
from typing import Callable, Awaitable

# Add src to path for any local imports
sys.path.insert(0, "src")

from agentica import spawn
from agentica.logging.agent_listener import PrintOnlyListener


async def test_scenario_1_agent_in_scope():
    """Pass entire agent instance to another agent's scope."""
    print("\n" + "="*60)
    print("SCENARIO 1: Agent instance in scope")
    print("="*60)

    try:
        # Create StateKeeper agent
        state_keeper = await spawn(
            premise="You are a state keeper. Remember facts told to you. When asked, recall them.",
            listener=PrintOnlyListener,
        )

        # Store a fact
        await state_keeper.call(str, "Remember this: The secret code is ALPHA-7")
        print("✓ StateKeeper stored: 'The secret code is ALPHA-7'")

        # Verify it remembers
        recall = await state_keeper.call(str, "What is the secret code?")
        print(f"✓ StateKeeper recalls: {recall}")

        # Create Query agent with StateKeeper in scope
        query_agent = await spawn(
            premise="You can query the state_keeper agent to get information.",
            scope={"state_keeper": state_keeper},
            listener=PrintOnlyListener,
        )

        # Try to query via the other agent
        result = await query_agent.call(
            str,
            "Ask the state_keeper what the secret code is and tell me."
        )
        print(f"✓ QueryAgent result: {result}")

        await state_keeper.close()
        await query_agent.close()
        return True, result

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False, str(e)


async def test_scenario_2_call_method_in_scope():
    """Pass agent's call method to scope."""
    print("\n" + "="*60)
    print("SCENARIO 2: Agent.call method in scope")
    print("="*60)

    try:
        # Create StateKeeper
        state_keeper = await spawn(
            premise="You remember facts. The password is BETA-9.",
            listener=PrintOnlyListener,
        )

        # Verify state
        check = await state_keeper.call(str, "What is the password?")
        print(f"✓ StateKeeper knows: {check}")

        # Create Query agent with call method in scope
        query_agent = await spawn(
            premise="You have access to ask_keeper function to query information.",
            scope={"ask_keeper": state_keeper.call},
            listener=PrintOnlyListener,
        )

        result = await query_agent.call(
            str,
            "Use ask_keeper to find out what the password is."
        )
        print(f"✓ QueryAgent result: {result}")

        await state_keeper.close()
        await query_agent.close()
        return True, result

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False, str(e)


async def test_scenario_3_wrapper_function():
    """Pass a wrapper function that calls the agent."""
    print("\n" + "="*60)
    print("SCENARIO 3: Wrapper function in scope")
    print("="*60)

    try:
        # Create StateKeeper
        state_keeper = await spawn(
            premise="You are a memory bank. Remember: Project name is GAMMA.",
            listener=PrintOnlyListener,
        )

        # Verify
        check = await state_keeper.call(str, "What is the project name?")
        print(f"✓ StateKeeper knows: {check}")

        # Create wrapper function
        async def query_memory(question: str) -> str:
            """Query the state keeper's memory."""
            return await state_keeper.call(str, question)

        # Create Query agent with wrapper
        query_agent = await spawn(
            premise="You have query_memory(question) to ask about stored information.",
            scope={"query_memory": query_memory},
            listener=PrintOnlyListener,
        )

        result = await query_agent.call(
            str,
            "Use query_memory to find out the project name."
        )
        print(f"✓ QueryAgent result: {result}")

        await state_keeper.close()
        await query_agent.close()
        return True, result

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False, str(e)


async def test_scenario_4_bidirectional():
    """Test if two agents can communicate bidirectionally."""
    print("\n" + "="*60)
    print("SCENARIO 4: Bidirectional communication")
    print("="*60)

    try:
        # This is tricky - we need to create both agents but wire them together
        # We'll use a shared state dict as a bridge

        shared_state = {"messages": []}

        async def send_to_bob(message: str) -> str:
            shared_state["messages"].append(("alice", message))
            return f"Sent to Bob: {message}"

        async def send_to_alice(message: str) -> str:
            shared_state["messages"].append(("bob", message))
            return f"Sent to Alice: {message}"

        async def get_messages() -> str:
            return str(shared_state["messages"])

        alice = await spawn(
            premise="You are Alice. You can send messages to Bob using send_to_bob().",
            scope={"send_to_bob": send_to_bob, "get_messages": get_messages},
            listener=PrintOnlyListener,
        )

        bob = await spawn(
            premise="You are Bob. You can send messages to Alice using send_to_alice().",
            scope={"send_to_alice": send_to_alice, "get_messages": get_messages},
            listener=PrintOnlyListener,
        )

        # Alice sends
        await alice.call(str, "Send a greeting to Bob saying 'Hello Bob!'")
        print(f"✓ Messages after Alice: {shared_state['messages']}")

        # Bob responds
        await bob.call(str, "Send a reply to Alice saying 'Hi Alice!'")
        print(f"✓ Messages after Bob: {shared_state['messages']}")

        # Check if Alice can see Bob's message
        alice_view = await alice.call(str, "Check get_messages() and tell me what Bob said.")
        print(f"✓ Alice sees: {alice_view}")

        await alice.close()
        await bob.close()
        return True, shared_state["messages"]

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False, str(e)


async def main():
    print("="*60)
    print("CROSS-AGENT COMMUNICATION TEST")
    print("="*60)

    results = {}

    # Run all scenarios
    results["scenario_1"] = await test_scenario_1_agent_in_scope()
    results["scenario_2"] = await test_scenario_2_call_method_in_scope()
    results["scenario_3"] = await test_scenario_3_wrapper_function()
    results["scenario_4"] = await test_scenario_4_bidirectional()

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for name, (success, result) in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")

    passed = sum(1 for s, _ in results.values() if s)
    print(f"\nTotal: {passed}/{len(results)} scenarios passed")

    return all(s for s, _ in results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
