#!/usr/bin/env python3
"""
Example usage of the erotetic verifier.

This demonstrates how to use the verifier programmatically.

USAGE:
    # Run with agentica extra
    uv run --extra agentica python example_erotetic_usage.py

REQUIREMENTS:
    - Python 3.12+
    - uv sync --extra agentica
    - Claude proxy at localhost:8080 (optional)
"""

import asyncio
import json
from scripts.agentica.erotetic_verifier import verify_resolution


async def example_1_empty_context():
    """Example 1: Empty context and no resolved answers."""
    print("\n" + "=" * 60)
    print("Example 1: Empty Context")
    print("=" * 60)

    result = await verify_resolution(
        context="",
        resolved={}
    )

    print("\nInput:")
    print("  Context: (empty)")
    print("  Resolved: {}")

    print("\nResult:")
    print(json.dumps(result, indent=2))

    print("\nExpectation: Should be isEmpty=True (no ambiguities in empty context)")


async def example_2_simple_task_no_resolution():
    """Example 2: Simple task with no resolved answers."""
    print("\n" + "=" * 60)
    print("Example 2: Task with No Resolution")
    print("=" * 60)

    context = "Build an authentication system for the API."

    result = await verify_resolution(
        context=context,
        resolved={}
    )

    print("\nInput:")
    print(f"  Context: {context}")
    print("  Resolved: {}")

    print("\nResult:")
    print(json.dumps(result, indent=2))

    print("\nExpectation: Should be isEmpty=False with topics like auth_method, session_duration, etc.")


async def example_3_partially_resolved():
    """Example 3: Task with partial resolution."""
    print("\n" + "=" * 60)
    print("Example 3: Partially Resolved Task")
    print("=" * 60)

    context = """
    Build an authentication system for the API.
    Users should be able to login and maintain sessions.
    Need proper error handling.
    """

    resolved = {
        "auth_method": "JWT",
        # Missing: session_duration, error_format, etc.
    }

    result = await verify_resolution(
        context=context,
        resolved=resolved
    )

    print("\nInput:")
    print(f"  Context: {context.strip()}")
    print(f"  Resolved: {json.dumps(resolved, indent=4)}")

    print("\nResult:")
    print(json.dumps(result, indent=2))

    print("\nExpectation: Should be isEmpty=False with remaining topics")


async def example_4_fully_resolved():
    """Example 4: Task with full resolution."""
    print("\n" + "=" * 60)
    print("Example 4: Fully Resolved Task")
    print("=" * 60)

    context = """
    Build an authentication system for the API.
    Users should be able to login and maintain sessions.
    Need proper error handling.
    """

    resolved = {
        "auth_method": "JWT",
        "session_duration": "24 hours",
        "error_format": "JSON with error codes and messages",
        "password_hashing": "bcrypt",
        "token_storage": "Redis",
        "rate_limiting": "100 requests per minute per IP",
    }

    result = await verify_resolution(
        context=context,
        resolved=resolved
    )

    print("\nInput:")
    print(f"  Context: {context.strip()}")
    print(f"  Resolved: {json.dumps(resolved, indent=4)}")

    print("\nResult:")
    print(json.dumps(result, indent=2))

    print("\nExpectation: Should be isEmpty=True or very low remainingCount with high confidence")


async def example_5_complex_task():
    """Example 5: Complex task with many ambiguities."""
    print("\n" + "=" * 60)
    print("Example 5: Complex Task")
    print("=" * 60)

    context = """
    Build a comprehensive e-commerce platform with:
    - User authentication and authorization
    - Product catalog with search and filtering
    - Shopping cart and checkout
    - Payment processing
    - Order management and tracking
    - Admin dashboard
    - Email notifications
    """

    resolved = {
        "auth_method": "OAuth2",
        "payment_gateway": "Stripe",
    }

    result = await verify_resolution(
        context=context,
        resolved=resolved
    )

    print("\nInput:")
    print(f"  Context: {context.strip()}")
    print(f"  Resolved: {json.dumps(resolved, indent=4)}")

    print("\nResult:")
    print(json.dumps(result, indent=2))

    print("\nExpectation: Should have many remainingTopics (database, search_engine, email_service, etc.)")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Erotetic Verifier - Usage Examples")
    print("=" * 60)

    examples = [
        example_1_empty_context,
        example_2_simple_task_no_resolution,
        example_3_partially_resolved,
        example_4_fully_resolved,
        example_5_complex_task,
    ]

    for i, example in enumerate(examples, 1):
        try:
            await example()
        except Exception as e:
            print(f"\n✗ Example {i} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("\nMake sure to run with:")
        print("  uv run --extra agentica python example_erotetic_usage.py")
        print("\nOr install dependencies:")
        print("  uv sync --extra agentica")
