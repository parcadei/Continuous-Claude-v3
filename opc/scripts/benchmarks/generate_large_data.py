#!/usr/bin/env python3
"""Generate more test data to show index impact."""

import os
import json
from scripts.core.env_loader import load_env
load_env()

import psycopg2
from sentence_transformers import SentenceTransformer

TOPICS = [
    "hook development patterns",
    "database migration",
    "TypeScript type errors",
    "authentication patterns",
    "python async patterns",
    "docker best practices",
    "postgresql performance",
    "embedding models",
    "testing strategies",
    "memory management",
    "error handling",
    "api design",
    "code review",
    "ci cd pipelines",
    "monitoring",
    "security practices",
    "git workflow",
    "containerization",
    "microservices",
    "api gateways",
    "cloud native",
    "kubernetes",
    "service mesh",
    "event driven",
    "message queues",
    "cache strategies",
    "rate limiting",
    "load balancing",
    "high availability",
    "disaster recovery",
]

def main():
    print("=" * 60)
    print("GENERATING LARGE TEST DATASET")
    print("=" * 60)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    conn = psycopg2.connect(db_url)
    print("Connected to PostgreSQL")

    # Check current count
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM archival_memory")
        current_count = cur.fetchone()[0]
    print(f"Current records: {current_count}")

    # Load model
    print(f"\nLoading BGE-large-en-v1.5 model...")
    embedder = SentenceTransformer("BAAI/bge-large-en-v1.5", device="cpu")
    print("Model loaded")

    # Generate many variations
    variations_per_topic = 100  # 30 topics * 100 = 3000 records
    all_learnings = []

    for topic in TOPICS:
        base = f"Learning about {topic}"
        for i in range(variations_per_topic):
            content = f"{base} variation {i}: Important insight about {topic} that helps with development."
            all_learnings.append(content)

    print(f"Total learnings to generate: {len(all_learnings)}")

    # Generate embeddings and insert in batches
    batch_size = 50
    inserted = 0

    for i in range(0, len(all_learnings), batch_size):
        batch = all_learnings[i:i + batch_size]
        embeddings = embedder.encode(batch).tolist()

        with conn.cursor() as cur:
            for content, embedding in zip(batch, embeddings):
                cur.execute("""
                    INSERT INTO archival_memory (session_id, agent_id, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                """, ("benchmark", "large_test", content, json.dumps({"type": "benchmark", "topic": "large"}), embedding))

        conn.commit()
        inserted += len(batch)
        if inserted % 500 == 0:
            print(f"  Inserted {inserted}/{len(all_learnings)}...")

    # Final count
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM archival_memory")
        final_count = cur.fetchone()[0]

    # Run benchmark with and without index
    import time

    test_query = "hook patterns"
    query_emb = embedder.encode([test_query]).tolist()[0]

    # Test WITHOUT index
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, 1 - (embedding <=> %s::vector) as sim
            FROM archival_memory
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (query_emb, query_emb))
        results_no_index = cur.fetchall()
    time_no_index = (time.perf_counter() - start) * 1000

    # Add HNSW index
    print(f"\nCreating HNSW index...")
    with conn.cursor() as cur:
        cur.execute("DROP INDEX IF EXISTS idx_archival_embedding_hnsw")
        cur.execute("""
            CREATE INDEX idx_archival_embedding_hnsw ON archival_memory
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
    conn.commit()

    # Test WITH index
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, 1 - (embedding <=> %s::vector) as sim
            FROM archival_memory
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (query_emb, query_emb))
        results_with_index = cur.fetchall()
    time_with_index = (time.perf_counter() - start) * 1000

    print(f"\n{'='*60}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*60}")
    print(f"Total records: {final_count}")
    print(f"Query: '{test_query}'")
    print(f"\nWITHOUT HNSW index:")
    print(f"   Time: {time_no_index:.1f}ms")
    print(f"   Results: {len(results_no_index)}")
    print(f"\nWITH HNSW index:")
    print(f"   Time: {time_with_index:.1f}ms")
    print(f"   Results: {len(results_with_index)}")
    print(f"\nSpeedup: {time_no_index/time_with_index:.1f}x faster")

    conn.close()
    print(f"\nDone!")


if __name__ == "__main__":
    main()
