#!/usr/bin/env python3
"""Generate test embeddings for performance testing."""

import os
import json
from pathlib import Path
from scripts.core.env_loader import load_env
load_env()

import psycopg2
from sentence_transformers import SentenceTransformer

# Sample learnings to insert
SAMPLE_LEARNINGS = [
    ("hook development patterns", "Hooks should be lightweight and fast. SessionStart hooks should not block startup."),
    ("database migration", "Database migrations track schema changes with version numbers. Use idempotent SQL."),
    ("TypeScript type errors", "TypeScript hooks require npm install in .claude/hooks/ before they work."),
    ("authentication patterns", "JWT validation requires checking both signature and expiration dates."),
    ("python async patterns", "Use asyncio for I/O-bound operations. Connection pooling improves performance."),
    ("docker best practices", "Use multi-stage builds to reduce image size. Don't run as root."),
    ("postgresql performance", "Use HNSW indexes for vector similarity search. IVFFlat is faster to build."),
    ("embedding models", "BGE-large-en-v1.5 provides 1024-dimensional embeddings with good quality."),
    ("testing strategies", "Use pytest fixtures for setup/teardown. Mock external dependencies."),
    ("memory management", "Clear caches periodically. Use LRU cache with size limits."),
    ("error handling", "Log errors with context. Use structured logging for better debugging."),
    ("api design", "Use RESTful conventions. Version your APIs. Document with OpenAPI."),
    ("code review", "Review for style, correctness, security, and performance. Be constructive."),
    ("ci cd pipelines", "Automate testing and deployment. Use parallel jobs for speed."),
    ("monitoring", "Track key metrics. Set up alerts for anomalies. Use structured logs."),
    ("security practices", "Validate input. Use parameterized queries. Encrypt sensitive data."),
    ("git workflow", "Use feature branches. Write meaningful commit messages. Rebase before merging."),
    ("containerization", "Use minimal base images. Pin versions. Scan for vulnerabilities."),
    ("microservices", "Design for failure. Use health checks. Implement circuit breakers."),
    ("api gateways", "Rate limit requests. Authenticate and authorize. Cache responses."),
]

# Generate variations of each learning
def generate_variations(base_learning, count=10):
    """Generate variations of a learning for testing."""
    import hashlib

    variations = []
    prefixes = ["", "Note:", "Remember:", "Important:", "Tip:", "Key point:"]
    suffixes = ["", "This is critical.", "Make sure to do this.", "Common mistake to avoid."]

    for i in range(count):
        prefix = prefixes[i % len(prefixes)]
        suffix = suffixes[i % len(suffixes)]
        content = f"{prefix} {base_learning} {suffix}".strip()
        variations.append(content)

    return variations


def main():
    print("=" * 60)
    print("GENERATING TEST EMBEDDING DATA")
    print("=" * 60)

    # Connect to database
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        print("Run: source opc/.env")
        return

    try:
        conn = psycopg2.connect(db_url)
        print("Connected to PostgreSQL")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # Check current count
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM archival_memory")
        current_count = cur.fetchone()[0]
    print(f"Current records: {current_count}")

    # Load model
    print(f"\nLoading BGE-large-en-v1.5 model...")
    embedder = SentenceTransformer("BAAI/bge-large-en-v1.5", device="cpu")
    print("Model loaded")

    # Generate test data
    print(f"\nGenerating test embeddings...")
    all_learnings = []
    for topic, learning in SAMPLE_LEARNINGS:
        variations = generate_variations(learning, 15)  # 15 variations each
        all_learnings.extend(variations)

    print(f"Total learnings to generate: {len(all_learnings)}")

    # Generate embeddings and insert
    batch_size = 32
    inserted = 0

    for i in range(0, len(all_learnings), batch_size):
        batch = all_learnings[i:i + batch_size]

        # Generate embeddings
        embeddings = embedder.encode(batch).tolist()

        # Insert batch
        with conn.cursor() as cur:
            for content, embedding in zip(batch, embeddings):
                cur.execute("""
                    INSERT INTO archival_memory (session_id, agent_id, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                """, ("benchmark", "test", content, json.dumps({"type": "benchmark", "topic": "testing"}), embedding))

        conn.commit()
        inserted += len(batch)
        print(f"  Inserted {inserted}/{len(all_learnings)}...")

    # Final count
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM archival_memory")
        final_count = cur.fetchone()[0]

    print(f"\nDone!")
    print(f"   Original: {current_count}")
    print(f"   Added: {inserted}")
    print(f"   Total: {final_count}")

    # Run quick benchmark
    print(f"\nRunning quick benchmark...")
    import time

    # Test vector search
    test_query = "hook patterns"
    query_emb = embedder.encode([test_query]).tolist()[0]

    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, 1 - (embedding <=> %s::vector) as sim
            FROM archival_memory
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (query_emb, query_emb))
        results = cur.fetchall()
    vector_time = (time.perf_counter() - start) * 1000

    print(f"\nVector search for '{test_query}':")
    print(f"   Time: {vector_time:.1f}ms")
    print(f"   Results: {len(results)}")

    conn.close()

    print(f"\nTo run full benchmark:")
    print(f"   uv run python scripts/benchmarks/embedding_benchmark.py")


if __name__ == "__main__":
    main()
