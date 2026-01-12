#!/usr/bin/env python3
"""Embedding benchmark fix for GTE-ModernBERT-base"""

import gc
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

OUTPUT_DIR = Path("/Users/grantray/Github/Continuous-Claude-v3/.claude/cache/agents/profiler")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_QUERIES = [
    {"name": "async_await_no_blocking", "query": "Python async function that calls await without blocking"},
    {"name": "auth_no_password", "query": "authentication WITHOUT password validation"},
    {"name": "sort_descending_not_ascending", "query": "sort list in DESCENDING order not ascending"},
    {"name": "goods_not_people", "query": "vehicle for transporting goods NOT people"},
    {"name": "connection_pool", "query": "create database connection pool efficiently"},
    {"name": "error_handling_production", "query": "What are best practices for error handling in production?"},
]

DOCUMENT_CORPUS = [
    "async def fetch_data(url): await asyncio.sleep(1); return await http.get(url)",
    "def synchronous_fetch(url): time.sleep(1); return requests.get(url)",
    "import asyncio; async def parallel_tasks(): await asyncio.gather(task1(), task2())",
    "password_hash = bcrypt.hash(password); auth = OAuth2Session(client_id)",
    "user = authenticate_token(token); if not user: return unauthorized()",
    "credentials = input('Enter password:'); if credentials == stored: login()",
    "sorted_list = sorted(data, reverse=True)  # descending order",
    "data.sort()  # ascending by default",
    "list.sort(key=lambda x: -x)  # descending",
    "delivery_truck = Vehicle(type='cargo', capacity=1000); transport_goods(truck)",
    "school_bus = Vehicle(type='passenger', seats=50); transport_people(bus)",
    "cargo_van = Ford_Transit(capacity=800, type='freight')",
    "engine = create_engine(url, pool_size=20, max_overflow=10); pool = engine.connect()",
    "conn = psycopg2.connect(dsn); cursor = conn.cursor()  # no pooling",
    "pool = PooledDB creator=psycopg2 mincached=5 maxcached=20",
    "try: result = risky_operation()\nexcept Exception as e: logger.error(e); retry()",
    "def handle_errors(func): wrapper: try: return func()\nexcept: fallback",
    "circuit_breaker = CircuitBreaker(failures=5, timeout=30); result = breaker.call()",
]

def get_memory_mb():
    import psutil
    return psutil.Process().memory_info().rss / (1024 * 1024)

def cosine_similarity(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

def test_model(model_name, model_id):
    from sentence_transformers import SentenceTransformer
    
    print(f"\n{'='*50}")
    print(f"Testing: {model_name}")
    print("-" * 50)
    
    gc.collect()
    torch.mps.empty_cache()
    mem_before = get_memory_mb()
    
    load_start = time.perf_counter()
    model = SentenceTransformer(model_id, device="mps")
    load_time = time.perf_counter() - load_start
    
    mem_after = get_memory_mb()
    print(f"Load time: {load_time:.2f}s")
    print(f"Memory delta: {mem_after - mem_before:.1f}MB")
    
    query_texts = [q["query"] for q in TEST_QUERIES]
    
    # Warmup
    for _ in range(3):
        _ = model.encode(query_texts, convert_to_numpy=True)
    
    # Timed encode
    encode_start = time.perf_counter()
    query_embeddings = model.encode(query_texts, convert_to_numpy=True)
    encode_time = time.perf_counter() - encode_start
    
    corpus_embeddings = model.encode(DOCUMENT_CORPUS, convert_to_numpy=True, show_progress_bar=False)
    
    results = {
        "model": model_name,
        "model_id": model_id,
        "load_time_seconds": round(load_time, 3),
        "query_encode_time_seconds": round(encode_time, 4),
        "avg_time_per_query_ms": round((encode_time / len(query_texts)) * 1000, 2),
        "memory_delta_mb": round(mem_after - mem_before, 1),
        "query_results": {}
    }
    
    for i, test_q in enumerate(TEST_QUERIES):
        query_emb = query_embeddings[i]
        similarities = [cosine_similarity(query_emb, emb) for emb in corpus_embeddings]
        sorted_indices = np.argsort(similarities)[::-1]
        
        results["query_results"][test_q["name"]] = {
            "query": test_q["query"],
            "top_match_similarity": round(similarities[sorted_indices[0]], 4),
            "second_match_similarity": round(similarities[sorted_indices[1]], 4),
            "spread": round(similarities[sorted_indices[0]] - similarities[sorted_indices[-1]], 4),
            "all_similarities": [round(s, 4) for s in sorted(similarities, reverse=True)[:5]],
        }
        
        print(f"  {test_q['name']}: {similarities[sorted_indices[0]]:.4f}")
    
    del model
    del corpus_embeddings
    gc.collect()
    torch.mps.empty_cache()
    
    return results

def main():
    print("=" * 70)
    print("EMBEDDING MODEL BENCHMARK - M4 MAX")
    print("=" * 70)
    
    all_results = {
        "benchmark_info": {
            "date": datetime.now().isoformat(),
            "hardware": "Apple M4 Max",
            "torch_version": torch.__version__,
        },
        "models": [],
    }
    
    models = [
        ("Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-0.6B"),
        ("BAAI/bge-large-en-v1.5", "BAAI/bge-large-en-v1.5"),
        ("BAAI/bge-m3", "BAAI/bge-m3"),
        ("GTE-ModernBERT-base", "Alibaba-NLP/gte-modernbert-base"),
    ]
    
    for name, model_id in models:
        try:
            result = test_model(name, model_id)
            all_results["models"].append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            all_results["models"].append({"model": name, "error": str(e)})
        time.sleep(1)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    successful = [m for m in all_results["models"] if "error" not in m]
    
    if successful:
        by_speed = sorted(successful, key=lambda m: m["load_time_seconds"])
        by_negation = sorted(successful, key=lambda m: np.mean([
            r["spread"] for r in m["query_results"].values()
        ]), reverse=True)
        
        print(f"\nFastest load: {by_speed[0]['model']} ({by_speed[0]['load_time_seconds']}s)")
        print(f"Best query discrimination: {by_negation[0]['model']}")
        
        print(f"\n{'Model':<28} {'Load':<8} {'Encode':<10} {'Per Query':<12} {'Avg Spread'}")
        print("-" * 70)
        for m in successful:
            avg_spread = np.mean([r["spread"] for r in m["query_results"].values()])
            print(f"{m['model']:<28} {m['load_time_seconds']:<8.2f} "
                  f"{m['query_encode_time_seconds']:<10.3f} "
                  f"{m['avg_time_per_query_ms']:<12.2f} "
                  f"{avg_spread:.4f}")
        
        all_results["summary"] = {
            "fastest_load_model": by_speed[0]["model"],
            "best_query_model": by_negation[0]["model"],
        }
    
    # Save
    output_file = OUTPUT_DIR / "embedding-benchmark-results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults: {output_file}")
    
    # Generate markdown
    generate_report(all_results)

def generate_report(results):
    md = f"""# Embedding Model Benchmark Report - M4 Max

## Executive Summary

**Hardware:** Apple M4 Max  
**Date:** {results["benchmark_info"]["date"]}

| Model | Load (s) | Encode (s) | Per Query | Memory | Score |
|-------|----------|------------|-----------|--------|-------|
"""
    for m in results.get("models", []):
        if "error" in m:
            continue
        avg_spread = np.mean([r["spread"] for r in m["query_results"].values()])
        md += f"| {m['model']} | {m['load_time_seconds']} | {m['query_encode_time_seconds']} | {m['avg_time_per_query_ms']}ms | {m['memory_delta_mb']}MB | {avg_spread:.4f} |\n"
    
    md += """
## Detailed Query Results

| Query | """ + " | ".join([m["model"][:15] for m in results.get("models", []) if "error" not in m]) + """ |
|-------|""" + "---|" * len([m for m in results.get("models", []) if "error" not in m]) + "\n"
    
    for qname in TEST_QUERIES:
        row = f"| {qname['name']} | "
        for m in results.get("models", []):
            if "error" in m:
                continue
            sim = m["query_results"].get(qname["name"], {}).get("top_match_similarity", "N/A")
            row += f"{sim} | "
        md += row + "\n"
    
    md += """
## Recommendations

"""
    if results.get("summary", {}).get("fastest_load_model"):
        md += f"- **Fastest cold load:** {results['summary']['fastest_load_model']}\n"
    if results.get("summary", {}).get("best_query_model"):
        md += f"- **Best query discrimination:** {results['summary']['best_query_model']}\n"
    
    md_file = OUTPUT_DIR / "embedding-benchmark-report.md"
    with open(md_file, "w") as f:
        f.write(md)
    print(f"Report: {md_file}")

if __name__ == "__main__":
    main()
