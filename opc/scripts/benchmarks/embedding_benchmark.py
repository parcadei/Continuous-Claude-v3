#!/usr/bin/env python3
"""Benchmark embedding search performance with direct SQL."""

import time
import json
import os
from pathlib import Path
from scripts.core.env_loader import load_env
load_env()

import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer


def check_indexes(conn):
    """Check what indexes exist."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    t.relname AS table_name,
                    i.relname AS index_name,
                    am.amname AS index_type,
                    pg_get_indexdef(i.oid) AS index_def
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_am am ON i.relam = am.oid
                WHERE t.relname IN ('archival_memory', 'handoffs', 'temporal_facts')
                ORDER BY t.relname, i.relname
            """)
            return cur.fetchall()
    except Exception:
        return []


def check_record_counts(conn):
    """Count records."""
    counts = {}
    for table in ["archival_memory", "handoffs"]:
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
        except Exception:
            counts[table] = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM temporal_facts")
            counts["temporal_facts"] = cur.fetchone()[0]
    except Exception:
        counts["temporal_facts"] = 0
    return counts


def benchmark_search(conn, embedder, query: str, runs: int = 5):
    """Run search benchmark and return timing stats."""

    # Generate embedding
    embed_times = []
    for _ in range(runs):
        start = time.perf_counter()
        embedding = embedder.encode([query]).tolist()[0]
        embed_times.append(time.perf_counter() - start)

    # Vector search timing (direct SQL)
    vector_times = []
    vector_results = []
    for _ in range(runs):
        try:
            start = time.perf_counter()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, content, metadata, created_at,
                           1 - (embedding <=> %s::vector) as similarity
                    FROM archival_memory
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT 10
                """, (embedding, embedding))
                vector_results = cur.fetchall()
            vector_times.append(time.perf_counter() - start)
            conn.commit()
        except Exception as e:
            conn.rollback()
            vector_times.append(0)
            vector_results = []

    # Text-only search timing
    text_times = []
    text_results = []
    for _ in range(runs):
        try:
            start = time.perf_counter()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                ts_query = ' & '.join(query.split()[:5])
                cur.execute("""
                    SELECT id, content, metadata, created_at,
                           ts_rank(to_tsvector('english', content), to_tsquery('english', %s)) as rank
                    FROM archival_memory
                    WHERE to_tsvector('english', content) @@ to_tsquery('english', %s)
                    ORDER BY rank DESC
                    LIMIT 10
                """, (ts_query, ts_query))
                text_results = cur.fetchall()
            text_times.append(time.perf_counter() - start)
            conn.commit()
        except Exception as e:
            conn.rollback()
            text_times.append(0)
            text_results = []

    return {
        "embedding": {
            "mean_ms": sum(embed_times) / len(embed_times) * 1000,
            "min_ms": min(embed_times) * 1000,
            "max_ms": max(embed_times) * 1000,
        },
        "vector_search": {
            "mean_ms": sum(vector_times) / len(vector_times) * 1000,
            "min_ms": min(vector_times) * 1000,
            "max_ms": max(vector_times) * 1000,
            "results": len(vector_results),
        },
        "text_search": {
            "mean_ms": sum(text_times) / len(text_times) * 1000,
            "min_ms": min(text_times) * 1000,
            "max_ms": max(text_times) * 1000,
            "results": len(text_results),
        },
    }


def main():
    print("=" * 60)
    print("EMBEDDING SEARCH BENCHMARK")
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

    # Check counts
    counts = check_record_counts(conn)
    print(f"\nRecord Counts:")
    for table, count in counts.items():
        print(f"   {table}: {count}")

    # Check indexes
    print(f"\nIndex Status:")
    indexes = check_indexes(conn)
    vector_indexes = [i for i in indexes if 'vector' in i['index_def'].lower() or 'ivfflat' in i['index_def'].lower() or 'hnsw' in i['index_def'].lower()]
    if vector_indexes:
        for idx in vector_indexes:
            print(f"   {idx['table_name']}: {idx['index_name']} ({idx['index_type']})")
    else:
        print("   No vector indexes found on memory tables!")
        print("   This means sequential scan - SLOW for large tables!")

    # Create embedder
    print(f"\nLoading BGE-large-en-v1.5 model...")
    embedder = SentenceTransformer("BAAI/bge-large-en-v1.5", device="cpu")
    print("Model loaded")

    # Run benchmarks
    queries = [
        "hook development patterns",
        "database migration",
        "TypeScript type errors",
        "authentication patterns",
    ]

    print(f"\nRunning benchmarks (5 runs each)...")
    all_results = {}

    for query in queries:
        print(f"\nQuery: '{query}'")
        results = benchmark_search(conn, embedder, query)
        all_results[query] = results

        print(f"   Embedding:  {results['embedding']['mean_ms']:.1f}ms")
        print(f"   Vector:     {results['vector_search']['mean_ms']:.1f}ms ({results['vector_search']['results']} results)")
        print(f"   Text:       {results['text_search']['mean_ms']:.1f}ms ({results['text_search']['results']} results)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    avg_embed = sum(r["embedding"]["mean_ms"] for r in all_results.values()) / len(all_results)
    avg_vector = sum(r["vector_search"]["mean_ms"] for r in all_results.values()) / len(all_results)
    avg_text = sum(r["text_search"]["mean_ms"] for r in all_results.values()) / len(all_results)

    print(f"\nAverage Times ({len(queries)} queries):")
    print(f"   Embedding: {avg_embed:.1f}ms")
    print(f"   Vector:    {avg_vector:.1f}ms")
    print(f"   Text:      {avg_text:.1f}ms")

    # Analysis
    print(f"\nAnalysis:")
    if avg_vector > 100:
        print(f"   Vector search SLOW ({avg_vector:.0f}ms)")
        print(f"   -> Add HNSW index to archival_memory for 10-100x speedup")
    else:
        print(f"   Vector search OK ({avg_vector:.0f}ms)")

    if avg_embed > 100:
        print(f"   Embedding generation SLOW ({avg_embed:.0f}ms)")
        print(f"   -> With 36GB M4 Max, try running on GPU")
    else:
        print(f"   Embedding generation OK ({avg_embed:.0f}ms)")

    if not vector_indexes:
        print(f"\n   To add HNSW index, run these SQL commands:")
        print(f"   -- This will speed up vector search by 10-100x")
        print(f"   CREATE INDEX ON archival_memory USING hnsw (embedding vector_cosine_ops)")
        print(f"     WITH (m = 16, ef_construction = 64);")

    conn.close()

    # Save results
    output = {
        "timestamp": time.time(),
        "record_counts": counts,
        "indexes": [{"table": i["table_name"], "index": i["index_name"], "type": i["index_type"]} for i in indexes],
        "results": all_results,
        "averages": {
            "embedding_ms": avg_embed,
            "vector_ms": avg_vector,
            "text_ms": avg_text,
        },
    }
    output_file = Path.home() / ".claude" / "cache" / "embedding_benchmark.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
