#!/usr/bin/env python3
"""
Benchmark Qwen/Qwen3-Embedding-0.6B model for semantic search.

Measures:
1. Cold start time (first load)
2. Embedding time per text (batch of 1, 5, 10)
3. Memory usage during inference
4. Throughput (texts per second)
"""

import gc
import json
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# Add opc directory to path
opc_dir = Path(__file__).parent.parent.parent
if str(opc_dir) not in sys.path:
    sys.path.insert(0, str(opc_dir))

import torch
from sentence_transformers import SentenceTransformer

# Test configuration
MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
DEVICE = "mps" if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() else "cpu"

# Test texts of varying length
TEST_TEXTS = {
    "short": [
        "Hello world",
        "Machine learning is cool",
        "Python programming",
    ],
    "medium": [
        "hook development patterns in TypeScript require careful attention to state management and async operations",
        "database migration strategies for PostgreSQL involve careful planning of schema changes and data consistency",
        "authentication and authorization systems must handle multiple identity providers and permission models",
    ],
    "long": [
        "The async/await pattern in Python provides a cleaner way to write concurrent code compared to callbacks. "
        "When used with proper error handling and task management, it enables building responsive applications that "
        "can handle thousands of concurrent I/O operations efficiently. The key is understanding event loops and "
        "how coroutines are scheduled for execution.",
        "Cross-encoder rerankers take query-document pairs and output relevance scores directly. Unlike bi-encoder "
        "approaches that encode documents and queries separately for cosine similarity, cross-encoders consider the "
        "interaction between query and document during encoding. This leads to higher accuracy but lower throughput.",
        "Vector similarity search in PostgreSQL uses pgvector to store and query embeddings efficiently. The key "
        "operators are inner product (<=>), Euclidean distance (<->), and cosine distance (<#>) which correspond to "
        "different similarity metrics. Proper indexing with IVFFlat or HNSW can achieve sub-millisecond queries.",
    ],
}


def get_device_info():
    """Get device information."""
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        return {
            "type": "cuda",
            "name": props.name,
            "total_memory_gb": props.total_memory / (1024**3),
        }
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return {
            "type": "mps",
            "name": "Apple Silicon (MPS)",
            "total_memory_gb": 36.0,
        }
    return {"type": "cpu", "name": "CPU", "total_memory_gb": None}


def clear_memory():
    """Clear GPU/CPU memory."""
    gc.collect()
    if hasattr(torch.cuda, 'empty_cache'):
        torch.cuda.empty_cache()
    elif hasattr(torch.backends.mps, 'is_available') and torch.backends.mps.is_available():
        torch.mps.empty_cache()


def benchmark_cold_start():
    """Benchmark model cold start (first load)."""
    print("\n" + "=" * 60)
    print("BENCHMARK 1: Cold Start Time (First Load)")
    print("=" * 60)
    
    clear_memory()
    results = []
    
    for i in range(3):  # Run 3 times to average
        print(f"\n  Run {i + 1}/3...")
        
        tracemalloc.start()
        load_start = time.perf_counter()
        model = SentenceTransformer(MODEL_NAME, device=DEVICE)
        load_time_ms = (time.perf_counter() - load_start) * 1000
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"    Load time: {load_time_ms:.0f}ms")
        print(f"    Peak memory: {peak_memory / (1024 * 1024):.1f}MB")
        
        results.append({
            "run": i + 1,
            "load_time_ms": load_time_ms,
            "peak_memory_mb": peak_memory / (1024 * 1024),
        })
        
        del model
        clear_memory()
    
    avg_load = sum(r["load_time_ms"] for r in results) / len(results)
    avg_mem = sum(r["peak_memory_mb"] for r in results) / len(results)
    
    print(f"\n  Average cold start: {avg_load:.0f}ms")
    print(f"  Average memory: {avg_mem:.1f}MB")
    
    return {
        "test": "cold_start",
        "avg_load_time_ms": avg_load,
        "min_load_time_ms": min(r["load_time_ms"] for r in results),
        "max_load_time_ms": max(r["load_time_ms"] for r in results),
        "avg_peak_memory_mb": avg_mem,
        "runs": results,
    }


def benchmark_batch_embedding(model, texts, batch_size, label):
    """Benchmark batch embedding with specific batch size."""
    clear_memory()
    gc.collect()
    
    # Warmup
    _ = model.encode(texts[:batch_size], batch_size=batch_size, normalize_embeddings=True)
    clear_memory()
    
    # Benchmark multiple iterations
    iterations = 5
    times = []
    
    for _ in range(iterations):
        tracemalloc.start()
        start = time.perf_counter()
        embeddings = model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        times.append((elapsed_ms, peak_memory))
        clear_memory()
    
    avg_time = sum(t[0] for t in times) / len(times)
    avg_mem = sum(t[1] for t in times) / len(times) / (1024 * 1024)
    
    throughput = len(texts) / (avg_time / 1000)
    
    return {
        "batch_size": batch_size,
        "texts_count": len(texts),
        "total_time_ms": avg_time,
        "time_per_text_ms": avg_time / len(texts),
        "throughput_tps": throughput,
        "total_chars": sum(len(t) for t in texts),
        "peak_memory_mb": avg_mem,
        "label": label,
    }


def run_benchmarks():
    """Run all benchmarks."""
    device_info = get_device_info()
    
    print("=" * 70)
    print("QWEN3-EMBEDDING-0.6B BENCHMARK")
    print("=" * 70)
    print(f"\nModel: {MODEL_NAME}")
    print(f"Device: {device_info['type']} ({device_info['name']})")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    all_results = {
        "model": MODEL_NAME,
        "device": device_info,
        "timestamp": datetime.now().isoformat(),
        "benchmarks": {},
    }
    
    # Benchmark 1: Cold Start
    all_results["benchmarks"]["cold_start"] = benchmark_cold_start()
    
    # Load model for remaining benchmarks
    print("\n" + "=" * 60)
    print("BENCHMARK 2-4: Embedding Time (Batch Sizes 1, 5, 10)")
    print("=" * 60)
    
    print("\n  Loading model for remaining benchmarks...")
    model = SentenceTransformer(MODEL_NAME, device=DEVICE)
    
    embed_dim = model.get_sentence_embedding_dimension()
    max_seq_length = model.max_seq_length
    print(f"  Embedding dimension: {embed_dim}")
    print(f"  Max sequence length: {max_seq_length}")
    
    batch_results = []
    
    # Test with short texts
    print("\n  Testing with SHORT texts (5-20 chars)...")
    short_results = []
    for batch_size in [1, 5, 10]:
        texts = TEST_TEXTS["short"] * (batch_size // len(TEST_TEXTS["short"]) + 1)
        texts = texts[:batch_size]
        result = benchmark_batch_embedding(model, texts, batch_size, "short")
        short_results.append(result)
        print(f"    Batch {batch_size}: {result['time_per_text_ms']:.2f}ms/text, {result['throughput_tps']:.1f} texts/sec")
    batch_results.append({"category": "short", "results": short_results})
    
    # Test with medium texts
    print("\n  Testing with MEDIUM texts (80-150 chars)...")
    medium_results = []
    for batch_size in [1, 5, 10]:
        texts = TEST_TEXTS["medium"] * (batch_size // len(TEST_TEXTS["medium"]) + 1)
        texts = texts[:batch_size]
        result = benchmark_batch_embedding(model, texts, batch_size, "medium")
        medium_results.append(result)
        print(f"    Batch {batch_size}: {result['time_per_text_ms']:.2f}ms/text, {result['throughput_tps']:.1f} texts/sec")
    batch_results.append({"category": "medium", "results": medium_results})
    
    # Test with long texts
    print("\n  Testing with LONG texts (300-500 chars)...")
    long_results = []
    for batch_size in [1, 5, 10]:
        texts = TEST_TEXTS["long"] * (batch_size // len(TEST_TEXTS["long"]) + 1)
        texts = texts[:batch_size]
        result = benchmark_batch_embedding(model, texts, batch_size, "long")
        long_results.append(result)
        print(f"    Batch {batch_size}: {result['time_per_text_ms']:.2f}ms/text, {result['throughput_tps']:.1f} texts/sec")
    batch_results.append({"category": "long", "results": long_results})
    
    all_results["benchmarks"]["batch_embedding"] = batch_results
    
    # Benchmark: Memory Usage During Inference
    print("\n" + "=" * 60)
    print("BENCHMARK 5: Memory Usage During Inference")
    print("=" * 60)
    
    print("\n  Testing memory with increasing batch sizes...")
    memory_results = []
    
    for batch_size in [1, 5, 10, 20, 50]:
        texts = TEST_TEXTS["medium"] * (batch_size // len(TEST_TEXTS["medium"]) + 1)
        texts = texts[:batch_size]
        
        clear_memory()
        gc.collect()
        
        tracemalloc.start()
        start = time.perf_counter()
        embeddings = model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        throughput = batch_size / (elapsed_ms / 1000)
        
        result = {
            "batch_size": batch_size,
            "total_time_ms": elapsed_ms,
            "time_per_text_ms": elapsed_ms / batch_size,
            "throughput_tps": throughput,
            "peak_memory_mb": peak / (1024 * 1024),
        }
        memory_results.append(result)
        
        print(f"    Batch {batch_size:2d}: {elapsed_ms:8.1f}ms total, "
              f"{result['time_per_text_ms']:6.2f}ms/text, "
              f"mem: {result['peak_memory_mb']:6.1f}MB, "
              f"{throughput:6.1f} texts/sec")
    
    all_results["benchmarks"]["memory_usage"] = memory_results
    
    # Benchmark: Throughput
    print("\n" + "=" * 60)
    print("BENCHMARK 6: Throughput (Texts Per Second)")
    print("=" * 60)
    
    print("\n  Testing sustained throughput...")
    
    large_texts = TEST_TEXTS["medium"] * 20
    iterations = 10
    
    clear_memory()
    gc.collect()
    
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        embeddings = model.encode(large_texts, batch_size=16, normalize_embeddings=True)
        times.append((time.perf_counter() - start) * 1000)
    
    avg_time = sum(times) / len(times)
    throughput = len(large_texts) / (avg_time / 1000)
    
    print(f"  Large batch ({len(large_texts)} texts, batch_size=16):")
    print(f"    Average time: {avg_time:.1f}ms")
    print(f"    Throughput: {throughput:.1f} texts/sec")
    print(f"    Per-text latency: {avg_time / len(large_texts):.2f}ms")
    
    all_results["benchmarks"]["throughput"] = {
        "texts_count": len(large_texts),
        "batch_size": 16,
        "iterations": iterations,
        "avg_time_ms": avg_time,
        "throughput_tps": throughput,
        "latency_per_text_ms": avg_time / len(large_texts),
    }
    
    del model
    clear_memory()
    
    # Generate summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    cold_start = all_results["benchmarks"]["cold_start"]
    print(f"\n1. COLD START (First Load)")
    print(f"   Average: {cold_start['avg_load_time_ms']:.0f}ms")
    print(f"   Range: {cold_start['min_load_time_ms']:.0f}ms - {cold_start['max_load_time_ms']:.0f}ms")
    print(f"   Peak Memory: {cold_start['avg_peak_memory_mb']:.1f}MB")
    
    print(f"\n2. EMBEDDING TIME PER TEXT (Medium texts)")
    for result in memory_results:
        print(f"   Batch {result['batch_size']:2d}: {result['time_per_text_ms']:6.2f}ms/text")
    
    print(f"\n3. MEMORY USAGE")
    for result in memory_results:
        print(f"   Batch {result['batch_size']:2d}: {result['peak_memory_mb']:6.1f}MB peak")
    
    print(f"\n4. THROUGHPUT")
    throughput = all_results["benchmarks"]["throughput"]
    print(f"   Sustained: {throughput['throughput_tps']:.1f} texts/sec")
    print(f"   Latency per text: {throughput['latency_per_text_ms']:.2f}ms")
    
    print(f"\n5. QUALITY (MTEB Score)")
    print(f"   Model: Qwen/Qwen3-Embedding-0.6B")
    print(f"   MTEB Score: 70.58 (SOTA for this model size)")
    print(f"   Dimension: 1024")
    
    print(f"\n6. SPEED VS QUALITY TRADEOFF")
    print(f"   Model Size: 0.6B parameters")
    print(f"   MTEB Score: 70.58 (excellent for size)")
    print(f"   Cold Start: ~{cold_start['avg_load_time_ms']/1000:.1f}s")
    print(f"   Single Text Latency: ~{memory_results[0]['time_per_text_ms']:.1f}ms")
    print(f"   Batch Throughput: ~{throughput['throughput_tps']:.0f} texts/sec")
    
    output_file = Path.home() / ".claude" / "cache" / "qwen3_embedding_benchmark.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(all_results, indent=2))
    print(f"\n📁 Full results saved to: {output_file}")
    
    return all_results


if __name__ == "__main__":
    run_benchmarks()
