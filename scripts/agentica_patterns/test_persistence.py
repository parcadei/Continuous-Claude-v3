#!/usr/bin/env python3
"""
Test Agentica state persistence across multiple agent.call() invocations.

USAGE:
    S_M_BASE_URL="http://localhost:2345" \
    .venv-agentica/bin/python scripts/agentica/test_persistence.py
"""

import asyncio


async def test_persistence():
    from agentica import spawn

    print("=== Testing Agentica State Persistence ===\n")

    # Create agent with a simple memory variable
    agent = await spawn(
        premise="""You are a note-taking assistant.
You have a variable 'notes' that stores information across calls.
When asked to remember something, append it to notes.
When asked to recall, return all notes.""",
    )

    # First call - store something
    print("Call 1: Remembering 'The capital of France is Paris'")
    result1 = await agent.call(str, "Remember: The capital of France is Paris")
    print(f"Response: {result1[:200]}...\n")

    # Second call - store more
    print("Call 2: Remembering 'Python was created in 1991'")
    result2 = await agent.call(str, "Remember: Python was created in 1991")
    print(f"Response: {result2[:200]}...\n")

    # Third call - recall everything
    print("Call 3: Recalling all notes")
    result3 = await agent.call(str, "What do you remember? List all the facts I told you.")
    print(f"Response: {result3}\n")

    # Check token usage
    usage = agent.total_usage()
    print(f"=== Token Usage ===")
    print(f"Input tokens: {usage.input_tokens}")
    print(f"Output tokens: {usage.output_tokens}")
    print(f"Total tokens: {usage.total_tokens}")

    return {
        "calls": 3,
        "final_recall": result3,
        "usage": {
            "input": usage.input_tokens,
            "output": usage.output_tokens,
            "total": usage.total_tokens
        }
    }


if __name__ == "__main__":
    result = asyncio.run(test_persistence())
    print(f"\n=== Test Complete ===")
    print(f"State persisted: {'Paris' in result['final_recall'] and 'Python' in result['final_recall']}")
