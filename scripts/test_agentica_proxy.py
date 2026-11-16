#!/usr/bin/env python3
"""Test Agentica with Claude proxy.

Requires:
1. Claude proxy running at localhost:8081
2. Agentica server at localhost:2345 with INFERENCE_ENDPOINT_URL set

Usage:
    uv run python scripts/test_agentica_proxy.py
"""

import asyncio
import os

# Point to local server
os.environ.setdefault("AGENTICA_SERVER_URL", "http://localhost:2345")


async def main():
    from agentica import spawn

    print("Creating agent via local Agentica server...")
    print("(Server should route LLM calls to Claude proxy)")

    agent = await spawn(
        premise="You are a helpful assistant. Keep responses brief.",
    )

    print("Agent created. Sending test query...")

    response = await agent.call(str, "Say hello in exactly one word.")

    print(f"\nResponse: {response}")
    print(f"Token usage: {agent.total_usage()}")


if __name__ == "__main__":
    asyncio.run(main())
