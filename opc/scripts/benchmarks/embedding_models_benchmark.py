#!/usr/bin/env python3
"""
Comprehensive Embedding Model Benchmark

Tests multiple embedding models optimized for:
- Apple Silicon (MPS/MacBook Pro M4 Max)
- NVIDIA CUDA (if available)
- CPU fallback

Measures:
- Embedding generation time
- Memory usage (peak VRAM/RAM)
- Throughput (tokens/sec)
- Quality (via semantic similarity consistency)
"""

import asyncio
import gc
import json
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup path
from scripts.core.env_loader import load_env
load_env()

# Detect hardware
def detect_hardware():
    """Detect available hardware for optimization."""
    info = {
        "device": "cpu",
        "cuda": False,
        "mps": False,
        "apple_silicon": False,
        "gpu_name": None,
        "gpu_memory": None,
        "cpu_count": os.cpu_count(),
    }

    try:
        import torch
        if torch.cuda.is_available():
            info["device"] = "cuda"
            info["cuda"] = True
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            info["device"] = "mps"
            info["mps"] = True
            info["apple_silicon"] = True
            # Get Apple Silicon info
            try:
                import subprocess
                result = subprocess.run(
                    ["sysctl", "hw.model"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    info["gpu_name"] = result.stdout.split(": ")[-1].strip()
            except:
                info["gpu_name"] = "Apple Silicon"
            # Approximate unified memory
            try:
                result = subprocess.run(
                    ["sysctl", "hw.memsize"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    mem_bytes = int(result.stdout.split(": ")[-1].strip())
                    info["gpu_memory"] = mem_bytes / (1024**3)
            except:
                info["gpu_memory"] = 36.0  # Default assumption
    except Exception as e:
        print(f"Hardware detection error: {e}")

    return info


# Model configurations
EMBEDDING_MODELS = {
    # High quality / reasonable size (recommended for production)
    "gte-modernbert-base": {
        "name": "Alibaba-NLP/gte-modernbert-base",
        "mteb_score": 64.5,
        "dimensions": 768,
        "vram_estimate_gb": 2.0,
        "max_tokens": 512,
        "multilingual": False,
        "code_specific": False,
        "description": "Highest MTEB score, lowest memory - BEST OVERALL",
    },
    "bge-large-en-v1.5": {
        "name": "BAAI/bge-large-en-v1.5",
        "mteb_score": 64.1,
        "dimensions": 1024,
        "vram_estimate_gb": 4.0,
        "max_tokens": 512,
        "multilingual": False,
        "code_specific": False,
        "description": "Best English-only, proven quality",
    },
    "bge-m3": {
        "name": "BAAI/bge-m3",
        "mteb_score": 63.2,
        "dimensions": 1024,
        "vram_estimate_gb": 4.0,
        "max_tokens": 512,
        "multilingual": True,
        "code_specific": False,
        "description": "100+ languages, dense/sparse/ColBERT modes",
    },
    "jina-embeddings-v3": {
        "name": "jinaai/jina-embeddings-v3",
        "mteb_score": 64.1,
        "dimensions": 1024,
        "vram_estimate_gb": 5.0,
        "max_tokens": 8192,
        "multilingual": True,
        "code_specific": False,
        "description": "High quality, long context",
    },

    # Code-specific models
    "jina-code-embeddings-1.5b": {
        "name": "jinaai/jina-code-embeddings-1.5b",
        "mteb_score": None,  # Code-specific
        "dimensions": 1536,
        "vram_estimate_gb": 3.0,
        "max_tokens": 8192,
        "multilingual": False,
        "code_specific": True,
        "description": "Best code embeddings, 1.5B params",
    },
    "nomic-embed-code-v1.5": {
        "name": "nomic-ai/nomic-embed-code-v1.5",
        "mteb_score": 62.0,
        "dimensions": 768,
        "vram_estimate_gb": 10.0,
        "max_tokens": 2048,
        "multilingual": False,
        "code_specific": True,
        "description": "Specialized code embeddings",
    },

    # Efficient models (battery/quick tasks)
    "bge-small-en-v1.5": {
        "name": "BAAI/bge-small-en-v1.5",
        "mteb_score": 8.4,  # Relative score (not MTEB)
        "dimensions": 512,
        "vram_estimate_gb": 0.5,
        "max_tokens": 512,
        "multilingual": False,
        "code_specific": False,
        "description": "Fastest with good quality",
    },
    "all-MiniLM-L6-v2": {
        "name": "sentence-transformers/all-MiniLM-L6-v2",
        "mteb_score": 8.2,  # Relative score
        "dimensions": 384,
        "vram_estimate_gb": 0.1,
        "max_tokens": 256,
        "multilingual": False,
        "code_specific": False,
        "description": "Lightest model, fastest inference",
    },
    "e5-small-v2": {
        "name": "intfloat/e5-small-v2",
        "mteb_score": 8.0,  # Relative score
        "dimensions": 384,
        "vram_estimate_gb": 0.2,
        "max_tokens": 512,
        "multilingual": False,
        "code_specific": False,
        "description": "CPU-optimized, good for battery",
    },
}

# Test queries - mix of general and code-specific
BENCHMARK_QUERIES = [
    "hook development patterns in TypeScript",
    "database migration strategies",
    "authentication and authorization patterns",
    "async Python programming best practices",
    "Docker container optimization",
    "def fibonacci(n): return fibonacci(n-1) + fibonacci(n-2)",
    "class DatabaseConnection: def connect(self): pass",
    "REST API design principles",
    "PostgreSQL vector similarity search",
    "machine learning model deployment",
]

# Code-specific queries
CODE_QUERIES = [
    "function calculateAverage(numbers: number[]): number {",
    "interface UserAuthentication { token: string; refresh: boolean; }",
    "async def process_data(data: list[str]) -> dict:",
    "public class Repository<T> where T: Entity {",
    "SELECT * FROM users WHERE email LIKE '%@domain.com%'",
    "def quicksort(arr): return quicksort([x for x in arr if x < pivot])",
]


@dataclass
class ModelBenchmarkResult:
    """Results from benchmarking a single model."""
    model_key: str
    model_name: str
    description: str
    device: str
    mteb_score: float | None
    dimensions: int

    # Timing (ms)
    load_time_ms: float = 0.0
    first_embed_ms: float = 0.0
    avg_embed_ms: float = 0.0
    min_embed_ms: float = 0.0
    max_embed_ms: float = 0.0

    # Throughput
    avg_tokens_per_sec: float = 0.0

    # Memory
    peak_memory_mb: float = 0.0
    memory_per_embed_mb: float = 0.0

    # Quality metrics
    similarity_consistency: float = 0.0  # How consistent are similar queries

    # Status
    loaded_successfully: bool = False
    error_message: str = ""

    # Hardware info
    hardware_info: dict = field(default_factory=dict)


def get_device_config(hardware_info: dict) -> dict:
    """Get optimal device configuration for the model."""
    config = {
        "device": hardware_info.get("device", "cpu"),
        "dtype": "float32",
    }

    if hardware_info.get("mps"):
        # Apple Silicon MPS
        config.update({
            "device": "mps",
            "dtype": "float16",
        })
    elif hardware_info.get("cuda"):
        # NVIDIA CUDA
        config.update({
            "device": "cuda",
            "dtype": "float16",
        })

    return config


def get_optimal_batch_size(model_key: str, hardware_info: dict) -> int:
    """Get optimal batch size based on model and hardware."""
    base_sizes = {
        "gte-modernbert-base": 32,
        "bge-large-en-v1.5": 16,
        "bge-m3": 16,
        "jina-embeddings-v3": 8,
        "jina-code-embeddings-1.5b": 8,
        "nomic-embed-code-v1.5": 4,
        "bge-small-en-v1.5": 64,
        "all-MiniLM-L6-v2": 128,
        "e5-small-v2": 64,
    }

    base = base_sizes.get(model_key, 32)

    # Adjust for hardware
    if hardware_info.get("mps"):
        # Apple Silicon - use larger batches with unified memory
        return base * 2
    elif hardware_info.get("cuda"):
        gpu_memory = hardware_info.get("gpu_memory", 8)
        if gpu_memory >= 24:  # RTX 4090, A100
            return base * 4
        elif gpu_memory >= 12:  # RTX 3060, 4070
            return base * 2
        else:
            return base

    return base


async def benchmark_model(model_key: str, config: dict, hardware_info: dict) -> ModelBenchmarkResult:
    """Benchmark a single embedding model."""
    result = ModelBenchmarkResult(
        model_key=model_key,
        model_name=EMBEDDING_MODELS[model_key]["name"],
        description=EMBEDDING_MODELS[model_key]["description"],
        device=config.get("device", "cpu"),
        mteb_score=EMBEDDING_MODELS[model_key].get("mteb_score"),
        dimensions=EMBEDDING_MODELS[model_key]["dimensions"],
        hardware_info=hardware_info,
    )

    # Check if code-specific model
    is_code_model = EMBEDDING_MODELS[model_key].get("code_specific", False)
    queries = CODE_QUERIES if is_code_model else BENCHMARK_QUERIES

    try:
        from sentence_transformers import SentenceTransformer
        import torch

        # Calculate batch size
        batch_size = get_optimal_batch_size(model_key, hardware_info)

        # Start memory tracking
        tracemalloc.start()

        # Load model with optimal settings
        load_start = time.perf_counter()

        model = SentenceTransformer(
            EMBEDDING_MODELS[model_key]["name"],
            device=config["device"],
            model_kwargs={
                "low_cpu_mem_usage": True,
            },
        )
        # Set dtype after creation
        if hasattr(model, 'tensor') and config["dtype"] == "float16":
            model.torch_dtype = torch.float16

        # Optimize for inference
        if hasattr(model, 'tokenizer'):
            model.tokenizer.padding_side = "right"

        result.load_time_ms = (time.perf_counter() - load_start) * 1000

        # Warmup
        _ = model.encode(["warmup query"], batch_size=1, normalize_embeddings=True)
        gc.collect()
        if hardware_info.get("mps"):
            torch.mps.empty_cache()

        # Benchmark encoding
        embed_times = []
        queries_batch = queries[:min(10, len(queries))]

        for _ in range(3):  # Multiple passes for accuracy
            start = time.perf_counter()
            embeddings = model.encode(
                queries_batch,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            embed_times.append((time.perf_counter() - start) * 1000)

            if hardware_info.get("mps"):
                torch.mps.empty_cache()
            gc.collect()

        # Calculate statistics
        result.first_embed_ms = embed_times[0]
        result.avg_embed_ms = sum(embed_times) / len(embed_times)
        result.min_embed_ms = min(embed_times)
        result.max_embed_ms = max(embed_times)

        # Calculate throughput (tokens/sec)
        total_tokens = sum(len(q.split()) for q in queries_batch)
        result.avg_tokens_per_sec = (total_tokens / (result.avg_embed_ms / 1000))

        # Memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result.peak_memory_mb = peak / (1024 * 1024)

        # Calculate similarity consistency (semantic coherence)
        # Compare embeddings of semantically similar queries
        similar_pairs = [
            ("hook development patterns", "hooks in TypeScript for Claude Code"),
            ("database migration", "schema migration strategies"),
        ]
        similarity_scores = []

        for q1, q2 in similar_pairs:
            try:
                emb1 = model.encode([q1], normalize_embeddings=True)
                emb2 = model.encode([q2], normalize_embeddings=True)
                similarity = float(torch.nn.functional.cosine_similarity(
                    torch.tensor(emb1), torch.tensor(emb2)
                ))
                similarity_scores.append(similarity)
            except:
                pass

        if similarity_scores:
            result.similarity_consistency = sum(similarity_scores) / len(similarity_scores)

        result.loaded_successfully = True

        # Cleanup
        del model
        gc.collect()
        if hardware_info.get("mps"):
            torch.mps.empty_cache()

    except Exception as e:
        result.loaded_successfully = False
        result.error_message = str(e)[:200]

    return result


async def run_benchmarks(hardware_info: dict, model_keys: list[str] | None = None) -> list[ModelBenchmarkResult]:
    """Run benchmarks on all specified models."""
    if model_keys is None:
        model_keys = list(EMBEDDING_MODELS.keys())

    results = []
    config = get_device_config(hardware_info)

    print(f"\n{'='*70}")
    print(f"EMBEDDING MODEL BENCHMARK")
    print(f"{'='*70}")
    print(f"Hardware: {hardware_info.get('gpu_name', 'CPU')}")
    print(f"Device: {config['device']}")
    print(f"Models to test: {len(model_keys)}")
    print(f"{'='*70}\n")

    for i, model_key in enumerate(model_keys, 1):
        model_info = EMBEDDING_MODELS[model_key]
        print(f"[{i}/{len(model_keys)}] Testing {model_key}...")
        print(f"  Model: {model_info['name']}")
        print(f"  Expected VRAM: {model_info['vram_estimate_gb']}GB")

        result = await benchmark_model(model_key, config, hardware_info)

        if result.loaded_successfully:
            print(f"  ✓ Loaded in {result.load_time_ms:.0f}ms")
            print(f"  ✓ Embed: {result.avg_embed_ms:.1f}ms avg ({result.avg_tokens_per_sec:.0f} tok/s)")
            print(f"  ✓ Peak memory: {result.peak_memory_mb:.1f}MB")
            if result.mteb_score:
                print(f"  ✓ MTEB: {result.mteb_score}")
        else:
            print(f"  ✗ Failed: {result.error_message}")

        results.append(result)
        print()

    return results


def analyze_results(results: list[ModelBenchmarkResult]) -> dict[str, Any]:
    """Analyze benchmark results and provide recommendations."""
    successful = [r for r in results if r.loaded_successfully]
    failed = [r for r in results if not r.loaded_successfully]

    analysis = {
        "timestamp": datetime.now().isoformat(),
        "total_models": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "recommendations": {},
        "rankings": {
            "by_speed": [],
            "by_quality": [],
            "by_efficiency": [],
            "by_throughput": [],
        },
        "failed_models": [r.model_key for r in failed],
    }

    if not successful:
        return analysis

    # Rank by speed (lower avg embed time is better)
    by_speed = sorted(successful, key=lambda x: x.avg_embed_ms)
    analysis["rankings"]["by_speed"] = [
        {"model": r.model_key, "avg_ms": r.avg_embed_ms, "rank": i+1}
        for i, r in enumerate(by_speed)
    ]

    # Rank by quality (MTEB score, higher is better)
    by_quality = sorted([r for r in successful if r.mteb_score], key=lambda x: x.mteb_score, reverse=True)
    analysis["rankings"]["by_quality"] = [
        {"model": r.model_key, "mteb": r.mteb_score, "rank": i+1}
        for i, r in enumerate(by_quality)
    ]

    # Rank by efficiency (quality / memory)
    efficiency_scores = []
    for r in successful:
        if r.mteb_score:
            efficiency = r.mteb_score / max(r.peak_memory_mb, 1)
            efficiency_scores.append((r, efficiency))
    by_efficiency = sorted(efficiency_scores, key=lambda x: x[1], reverse=True)
    analysis["rankings"]["by_efficiency"] = [
        {"model": r.model_key, "efficiency": score, "memory_mb": r.peak_memory_mb, "rank": i+1}
        for i, (r, score) in enumerate(by_efficiency)
    ]

    # Rank by throughput
    by_throughput = sorted(successful, key=lambda x: x.avg_tokens_per_sec, reverse=True)
    analysis["rankings"]["by_throughput"] = [
        {"model": r.model_key, "tok_per_sec": r.avg_tokens_per_sec, "rank": i+1}
        for i, r in enumerate(by_throughput)
    ]

    # Generate recommendations
    analysis["recommendations"] = {
        "best_overall": by_efficiency[0].model_key if by_efficiency else None,
        "best_quality": by_quality[0].model_key if by_quality else None,
        "best_speed": by_speed[0].model_key if by_speed else None,
        "best_throughput": by_throughput[0].model_key if by_throughput else None,
        "for_code_tasks": None,
        "for_production": None,
        "for_battery": None,
    }

    # Find best for code tasks
    code_models = [r for r in successful if EMBEDDING_MODELS[r.model_key].get("code_specific")]
    if code_models:
        analysis["recommendations"]["for_code_tasks"] = max(
            code_models, key=lambda x: x.mteb_score or 0
        ).model_key

    # Find best for production (balance of quality and efficiency)
    production_candidates = [r for r in successful if r.mteb_score and r.mteb_score > 60]
    if production_candidates:
        best_prod = sorted(production_candidates, key=lambda x: x.mteb_score / max(x.peak_memory_mb, 1), reverse=True)
        analysis["recommendations"]["for_production"] = best_prod[0].model_key

    # Find best for battery (fast and low memory)
    battery_models = [r for r in successful if r.avg_embed_ms < 50 and r.peak_memory_mb < 500]
    if battery_models:
        analysis["recommendations"]["for_battery"] = min(
            battery_models, key=lambda x: x.avg_embed_ms
        ).model_key

    return analysis


def print_summary(results: list[ModelBenchmarkResult], analysis: dict[str, Any]):
    """Print a formatted summary of results."""
    print(f"\n{'='*70}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*70}")

    successful = [r for r in results if r.loaded_successfully]

    # Overall stats
    print(f"\n✓ Successfully tested: {len(successful)}/{len(results)} models")
    if analysis.get("failed_models"):
        print(f"✗ Failed: {', '.join(analysis['failed_models'])}")

    # Recommendations
    recs = analysis.get("recommendations", {})
    print(f"\n🏆 RECOMMENDATIONS:")
    print(f"   Best Overall:     {recs.get('best_overall', 'N/A')}")
    print(f"   Best Quality:     {recs.get('best_quality', 'N/A')}")
    print(f"   Best Speed:       {recs.get('best_speed', 'N/A')}")
    print(f"   Best Throughput:  {recs.get('best_throughput', 'N/A')}")
    print(f"   For Code Tasks:   {recs.get('for_code_tasks', 'N/A')}")
    print(f"   For Production:   {recs.get('for_production', 'N/A')}")
    print(f"   For Battery:      {recs.get('for_battery', 'N/A')}")

    # Detailed rankings
    print(f"\n📊 RANKINGS:")
    print(f"\n   By Quality (MTEB):")
    for item in analysis["rankings"]["by_quality"][:3]:
        model_info = EMBEDDING_MODELS.get(item["model"], {})
        score = item.get("mteb", "N/A")
        print(f"      {item['rank']}. {item['model']} - MTEB: {score}")

    print(f"\n   By Speed (ms per embedding):")
    for item in analysis["rankings"]["by_speed"][:3]:
        print(f"      {item['rank']}. {item['model']} - {item['avg_ms']:.1f}ms")

    print(f"\n   By Efficiency (MTEB/MB):")
    for item in analysis["rankings"]["by_efficiency"][:3]:
        print(f"      {item['rank']}. {item['model']} - {item['efficiency']:.3f}")

    print(f"\n   By Throughput (tokens/sec):")
    for item in analysis["rankings"]["by_throughput"][:3]:
        print(f"      {item['rank']}. {item['model']} - {item['tok_per_sec']:.0f} tok/s")

    # Detailed table
    print(f"\n📋 DETAILED RESULTS:")
    print(f"   {'Model':<30} {'MTEB':>6} {'Time':>8} {'Tok/s':>10} {'Mem':>10} {'Status'}")
    print(f"   {'-'*30} {'-'*6} {'-'*8} {'-'*10} {'-'*10} {'-'*6}")

    for r in sorted(successful, key=lambda x: x.mteb_score or 0, reverse=True):
        mteb = f"{r.mteb_score:.1f}" if r.mteb_score else "N/A"
        time_str = f"{r.avg_embed_ms:.1f}ms"
        tok_str = f"{r.avg_tokens_per_sec:.0f}"
        mem_str = f"{r.peak_memory_mb:.0f}MB"
        status = "✓" if r.loaded_successfully else "✗"

        print(f"   {r.model_key:<30} {mteb:>6} {time_str:>8} {tok_str:>10} {mem_str:>10} {status}")

    print(f"\n{'='*70}")


def save_results(results: list[ModelBenchmarkResult], analysis: dict[str, Any], output_file: Path):
    """Save results to JSON file."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "analysis": analysis,
        "results": [asdict(r) for r in results],
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output, indent=2))
    print(f"\n📁 Results saved to: {output_file}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark embedding models")
    parser.add_argument("--models", "-m", nargs="+", help="Specific models to test")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    # Detect hardware
    hardware_info = detect_hardware()
    print(f"\nDetected hardware:")
    print(f"   Device: {hardware_info['device']}")
    print(f"   GPU: {hardware_info.get('gpu_name', 'N/A')}")
    print(f"   GPU Memory: {hardware_info.get('gpu_memory', 'N/A'):.1f}GB")
    print(f"   CPU Cores: {hardware_info.get('cpu_count', 'N/A')}")

    # Run benchmarks
    results = await run_benchmarks(hardware_info, args.models)

    # Analyze results
    analysis = analyze_results(results)

    # Print summary
    if not args.json:
        print_summary(results, analysis)

    # Save results
    output_file = Path(args.output) if args.output else Path.home() / ".claude" / "cache" / "embedding_benchmark_results.json"
    save_results(results, analysis, output_file)

    if args.json:
        # Output JSON for programmatic use
        print(json.dumps({"analysis": analysis, "results": [asdict(r) for r in results]}, indent=2))

    return results, analysis


if __name__ == "__main__":
    results, analysis = asyncio.run(main())
