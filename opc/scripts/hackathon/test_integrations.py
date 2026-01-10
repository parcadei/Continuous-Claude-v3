#!/usr/bin/env python3
"""Test all hackathon integrations.

Run this to verify everything works before the demo.

Usage:
    python -m scripts.hackathon.test_integrations
"""

import asyncio
import os
import sys


async def test_embeddings():
    """Test Jina embeddings."""
    print("\n" + "=" * 50)
    print("Testing Embeddings")
    print("=" * 50)

    from scripts.hackathon.embeddings import Embedder

    embedder = Embedder()
    print(f"Provider: {embedder._provider}")

    embedding = await embedder.embed("Hello world")
    print(f"✓ Embedding dimension: {len(embedding)}")

    # Test query vs passage task
    query_emb = await embedder.embed("search query", task="retrieval.query")
    doc_emb = await embedder.embed("document content", task="retrieval.passage")
    print(f"✓ Task-specific embeddings work")

    await embedder.close()
    return True


async def test_inference():
    """Test Fireworks AI inference."""
    print("\n" + "=" * 50)
    print("Testing Inference (Fireworks AI)")
    print("=" * 50)

    if not os.environ.get("FIREWORKS_API_KEY"):
        print("⚠ FIREWORKS_API_KEY not set, skipping")
        return False

    from scripts.hackathon.inference import LLM

    llm = LLM(model="fast")
    print(f"Model: {llm.model}")

    response = await llm.chat("Say 'test' and nothing else.")
    print(f"✓ Chat response: {response[:50]}...")

    # Test function calling
    result = await llm.call_function(
        "Get weather for Tokyo",
        functions=[{
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        }],
    )
    print(f"✓ Function calling: {result}")

    await llm.close()
    return True


async def test_mongodb():
    """Test MongoDB Atlas."""
    print("\n" + "=" * 50)
    print("Testing MongoDB Atlas")
    print("=" * 50)

    if not os.environ.get("MONGODB_URI"):
        print("⚠ MONGODB_URI not set, skipping")
        return False

    from scripts.hackathon.mongo_client import MongoClient

    client = MongoClient()
    await client.connect()

    # Store a test document
    doc_id = await client.store(
        "Test learning about hackathon integrations",
        metadata={"test": True}
    )
    print(f"✓ Stored document: {doc_id}")

    # Search
    results = await client.text_search("hackathon")
    print(f"✓ Text search found {len(results)} results")

    # Log a run
    run_id = await client.log_run(
        command="/test",
        status="completed",
        eval_passed=True,
    )
    print(f"✓ Logged run: {run_id}")

    await client.close()
    return True


async def test_eval_gate():
    """Test quality gate."""
    print("\n" + "=" * 50)
    print("Testing Quality Gate")
    print("=" * 50)

    from scripts.hackathon.eval_gate import QualityGate

    gate = QualityGate()

    # Good response
    result = await gate.check(
        input="What is Python?",
        output="Python is a high-level programming language known for its readability and versatility.",
        context="Python is a programming language.",
    )
    print(f"✓ Good response: passed={result.passed}, scores={result.scores}")

    # Bad response
    result = await gate.check(
        input="What is Python?",
        output="I hate this stupid question",
    )
    print(f"✓ Bad response: passed={result.passed}, failed={result.failed_metrics}")

    return True


async def test_hybrid_search():
    """Test hybrid search (the key MongoDB feature)."""
    print("\n" + "=" * 50)
    print("Testing Hybrid Search (RRF)")
    print("=" * 50)

    if not os.environ.get("MONGODB_URI"):
        print("⚠ MONGODB_URI not set, skipping")
        return False

    from scripts.hackathon.mongo_client import MongoClient
    from scripts.hackathon.embeddings import Embedder

    client = MongoClient()
    await client.connect()

    embedder = Embedder()

    # Store test documents with embeddings
    texts = [
        "MongoDB Atlas provides vector search capabilities",
        "Fireworks AI offers fast LLM inference",
        "Jina embeddings support multiple languages",
    ]

    for text in texts:
        embedding = await embedder.embed(text)
        await client.store(text, embedding=embedding)

    print(f"✓ Stored {len(texts)} documents with embeddings")

    # Hybrid search
    query = "vector search database"
    query_emb = await embedder.embed(query, task="retrieval.query")

    results = await client.hybrid_search(query, query_emb, limit=3)
    print(f"✓ Hybrid search found {len(results)} results")
    for r in results:
        print(f"  - {r['content'][:50]}... (RRF: {r.get('rrf_score', 0):.3f})")

    await embedder.close()
    await client.close()
    return True


async def main():
    """Run all tests."""
    print("=" * 50)
    print("CCv3 Hackathon Integration Tests")
    print("=" * 50)

    results = {
        "embeddings": await test_embeddings(),
        "inference": await test_inference(),
        "mongodb": await test_mongodb(),
        "eval_gate": await test_eval_gate(),
        "hybrid_search": await test_hybrid_search(),
    }

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL/SKIP"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'✓ ALL TESTS PASSED' if all_passed else '⚠ SOME TESTS FAILED/SKIPPED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
