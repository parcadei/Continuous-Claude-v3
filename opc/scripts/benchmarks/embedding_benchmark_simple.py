#!/usr/bin/env python3
"""
Simplified Embedding Model Benchmark
Tests key models and provides quick results
"""

import json
import os
import sys
import time
import tracemalloc
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

# Add opc directory to path
opc_dir = Path(__file__).parent.parent.parent
if str(opc_dir) not in sys.path:
    sys.path.insert(0, str(opc_dir))

import torch
from sentence_transformers import SentenceTransformer


# Key models to test (curated list)
MODELS = {
    # BGE series - proven, efficient
    "gte-modernbert-base": ("Alibaba-NLP/gte-modernbert-base", 64.5, 768),
    "bge-large-en-v1.5": ("BAAI/bge-large-en-v1.5", 64.1, 1024),
    "bge-m3": ("BAAI/bge-m3", 63.2, 1024),
    "bge-small-en-v1.5": ("BAAI/bge-small-en-v1.5", None, 512),
    # Qwen3 - NEW SOTA candidates (Apache 2.0 license)
    "qwen3-embedding-0.6b": ("Qwen/Qwen3-Embedding-0.6B", 70.58, 1024),
    "qwen3-embedding-4b": ("Qwen/Qwen3-Embedding-4B", 69.45, 1536),
    # ByteDance Seed-Embedding (NEW)
    "seed-embedding-1.6b": ("ByteDance-Seed/Seed-Embedding-1.6B", 70.5, 1024),
    # Reranker (for hybrid search)
    "qwen3-reranker-0.6b": ("Qwen/Qwen3-Reranker-0.6B", 65.80, 1024),
    # Efficient models
    "jina-code-1.5b": ("jinaai/jina-code-embeddings-1.5b", None, 1536),
    "nomic-embed-code": ("nomic-ai/nomic-embed-code-v1.5", 62.0, 768),
    "MiniLM-L6": ("sentence-transformers/all-MiniLM-L6-v2", None, 384),
}


@dataclass
class Result:
    model: str
    name: str
    mteb: float | None
    dims: int
    load_ms: float
    embed_ms: float
    tokens_sec: float
    peak_mem_mb: float
    success: bool
    error: str = ""


def detect_device():
    """Detect best device."""
    if torch.cuda.is_available():
        return "cuda", torch.cuda.get_device_name(0), torch.cuda.get_device_properties(0).total_memory / (1024**3)
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps", "Apple Silicon", 36.0  # Approximate for M4 Max
    return "cpu", "CPU", None


def benchmark_model(key, name, queries):
    """Benchmark a single model."""
    result = Result(
        model=key,
        name=name,
        mteb=MODELS[key][1],
        dims=MODELS[key][2],
        load_ms=0,
        embed_ms=0,
        tokens_sec=0,
        peak_mem_mb=0,
        success=False,
    )

    device, gpu_name, gpu_mem = detect_device()
    print(f"\n{'='*60}")
    print(f"Testing: {key}")
    print(f"Device: {device} ({gpu_name})")
    print(f"{'='*60}")

    try:
        tracemalloc.start()

        # Load model
        load_start = time.perf_counter()
        model = SentenceTransformer(name, device=device)
        result.load_ms = (time.perf_counter() - load_start) * 1000
        print(f"  Loaded in {result.load_ms:.0f}ms")

        # Warmup
        _ = model.encode(["warmup"], batch_size=1, normalize_embeddings=True)
        if device == "mps":
            torch.mps.empty_cache()
        gc = __import__('gc')
        gc.collect()

        # Benchmark encoding
        embed_times = []
        for _ in range(5):
            start = time.perf_counter()
            embeddings = model.encode(queries[:10], batch_size=8, normalize_embeddings=True)
            embed_times.append((time.perf_counter() - start) * 1000)
            if device == "mps":
                torch.mps.empty_cache()

        result.embed_ms = sum(embed_times) / len(embed_times)
        print(f"  Embed: {result.embed_ms:.1f}ms avg")

        # Calculate throughput
        total_tokens = sum(len(q.split()) for q in queries[:10])
        result.tokens_sec = total_tokens / (result.embed_ms / 1000)
        print(f"  Throughput: {result.tokens_sec:.0f} tok/s")

        # Memory
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result.peak_mem_mb = peak / (1024 * 1024)
        print(f"  Peak memory: {result.peak_mem_mb:.1f}MB")

        result.success = True

        # Cleanup
        del model
        if device == "mps":
            torch.mps.empty_cache()

    except Exception as e:
        result.success = False
        result.error = str(e)[:100]
        print(f"  ERROR: {e}")

    return result


def main():
    device, gpu_name, gpu_mem = detect_device()
    print(f"\n{'='*70}")
    print(f"EMBEDDING MODEL BENCHMARK")
    print(f"{'='*70}")
    print(f"Hardware: {gpu_name}")
    print(f"Device: {device}")
    if gpu_mem:
        print(f"GPU Memory: {gpu_mem:.1f}GB")

    # Test queries
    queries = [
        "hook development patterns in TypeScript",
        "database migration strategies",
        "authentication and authorization",
        "async Python programming best practices",
        "def fibonacci(n): return fibonacci(n-1) + fibonacci(n-2)",
        "class DatabaseConnection: def connect(self): pass",
        "REST API design principles",
        "PostgreSQL vector similarity search",
    ]

    results = []
    for key, (name, _, _) in MODELS.items():
        result = benchmark_model(key, name, queries)
        results.append(result)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    successful = [r for r in results if r.success]
    print(f"\n✓ Tested: {len(successful)}/{len(results)} models")

    # Sort by embed time
    by_speed = sorted(successful, key=lambda x: x.embed_ms)
    print(f"\n📊 BY SPEED (fastest first):")
    for i, r in enumerate(by_speed[:5], 1):
        print(f"   {i}. {r.model}: {r.embed_ms:.1f}ms, {r.tokens_sec:.0f} tok/s")

    # Sort by quality (MTEB)
    by_quality = sorted([r for r in successful if r.mteb], key=lambda x: x.mteb, reverse=True)
    print(f"\n📊 BY QUALITY (MTEB score):")
    for i, r in enumerate(by_quality[:5], 1):
        print(f"   {i}. {r.model}: MTEB {r.mteb}")

    # Sort by efficiency
    by_eff = sorted(successful, key=lambda x: (x.mteb or 0) / max(x.peak_mem_mb, 1), reverse=True)
    print(f"\n📊 BY EFFICIENCY (MTEB/GB RAM):")
    for i, r in enumerate(by_eff[:5], 1):
        mem_gb = r.peak_mem_mb / 1024
        eff = (r.mteb or 0) / max(mem_gb, 0.1)
        print(f"   {i}. {r.model}: {eff:.1f} (MTEB/{mem_gb:.1f}GB)")

    # Recommendations
    print(f"\n🏆 RECOMMENDATIONS:")
    if by_speed:
        print(f"   Fastest: {by_speed[0].model}")
    if by_quality:
        print(f"   Best Quality: {by_quality[0].model} (MTEB {by_quality[0].mteb})")
    if by_eff:
        print(f"   Best Efficiency: {by_eff[0].model}")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "device": device,
        "gpu": gpu_name,
        "results": [asdict(r) for r in results],
    }
    output_file = Path.home() / ".claude" / "cache" / "embedding_benchmark.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output, indent=2))
    print(f"\n📁 Results saved to: {output_file}")

    return results


if __name__ == "__main__":
    main()
