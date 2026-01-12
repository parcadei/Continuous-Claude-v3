#!/usr/bin/env python3
"""Auto-configuration for embedding performance based on hardware.

Detects GPU type (MPS/CUDA/CPU) and sets optimal parameters:
- Batch sizes
- Model choices
- Reranking thresholds
- Caching strategies

Usage:
    python embedding_config.py --benchmark    # Run benchmarks
    python embedding_config.py --config       # Print current config
    python embedding_config.py --apply        # Apply to .env
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

# Add opc to path
opc_dir = Path(__file__).parent.parent
if str(opc_dir) not in sys.path:
    sys.path.insert(0, str(opc_dir))


@dataclass
class HardwareConfig:
    """Hardware detection and optimal settings."""
    device: str
    gpu_name: str
    vram_gb: float
    embedding_batch_size: int
    reranker_batch_size: int
    enable_rerank_cache: bool
    rerank_threshold: float
    prewarm_models: bool


def detect_hardware() -> HardwareConfig:
    """Detect GPU and return optimal configuration."""
    import torch
    import psutil

    # Detect device
    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = "mps"
        gpu_name = "Apple Silicon (MPS)"
        # Estimate unified memory
        proc = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True
        )
        vram = int(proc.stdout.strip()) / (1024**3) if proc.returncode == 0 else 36.0
    else:
        device = "cpu"
        gpu_name = "CPU"
        vram = psutil.virtual_memory().total / (1024**3)

    # Configure based on device and VRAM
    if device == "cuda" and vram >= 24:
        # High-end NVIDIA GPU
        return HardwareConfig(
            device=device,
            gpu_name=gpu_name,
            vram_gb=vram,
            embedding_batch_size=32,
            reranker_batch_size=64,
            enable_rerank_cache=True,
            rerank_threshold=0.75,
            prewarm_models=True,
        )
    elif device == "cuda":
        # Regular NVIDIA GPU
        return HardwareConfig(
            device=device,
            gpu_name=gpu_name,
            vram_gb=vram,
            embedding_batch_size=16,
            reranker_batch_size=32,
            enable_rerank_cache=True,
            rerank_threshold=0.70,
            prewarm_models=True,
        )
    elif device == "mps" and vram >= 32:
        # M4 Max or similar (36GB+ unified)
        return HardwareConfig(
            device=device,
            gpu_name=gpu_name,
            vram_gb=vram,
            embedding_batch_size=10,
            reranker_batch_size=32,
            enable_rerank_cache=True,
            rerank_threshold=0.72,
            prewarm_models=True,
        )
    elif device == "mps":
        # M3 or smaller (8-18GB unified)
        return HardwareConfig(
            device=device,
            gpu_name=gpu_name,
            vram_gb=vram,
            embedding_batch_size=8,
            reranker_batch_size=16,
            enable_rerank_cache=True,
            rerank_threshold=0.68,
            prewarm_models=False,
        )
    else:
        # CPU fallback
        return HardwareConfig(
            device=device,
            gpu_name=gpu_name,
            vram_gb=vram,
            embedding_batch_size=4,
            reranker_batch_size=8,
            enable_rerank_cache=True,
            rerank_threshold=0.65,
            prewarm_models=False,
        )


def run_benchmarks(device: str) -> dict:
    """Run performance benchmarks for embedding models."""
    print(f"\n{'='*60}")
    print("BENCHMARKING EMBEDDING MODELS")
    print(f"{'='*60}")
    print(f"Device: {device}")
    print()

    from sentence_transformers import SentenceTransformer, CrossEncoder
    import torch

    results = {}

    # Benchmark Qwen3-Embedding-0.6B
    print("Testing: Qwen/Qwen3-Embedding-0.6B")
    start = time.perf_counter()
    model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device=device)
    load_time = (time.perf_counter() - start) * 1000
    print(f"  Cold load: {load_time:.0f}ms")

    queries = [
        "hook development patterns in TypeScript",
        "database migration strategies",
        "authentication and authorization",
        "async Python programming best practices",
        "REST API design principles",
    ] * 2

    start = time.perf_counter()
    embeddings = model.encode(queries, normalize_embeddings=True, batch_size=10)
    encode_time = (time.perf_counter() - start) * 1000
    throughput = len(queries) / (encode_time / 1000)

    print(f"  Batch encode ({len(queries)} texts): {encode_time:.1f}ms")
    print(f"  Throughput: {throughput:.0f} texts/sec")
    results["qwen_embed"] = {
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "load_ms": load_time,
        "encode_ms": encode_time,
        "throughput": throughput,
    }

    # Benchmark BGE Reranker
    print("\nTesting: BAAI/bge-reranker-base")
    start = time.perf_counter()
    reranker = CrossEncoder("BAAI/bge-reranker-base", device=device)
    load_time = (time.perf_counter() - start) * 1000
    print(f"  Cold load: {load_time:.0f}ms")

    docs = ["async def main(): pass"] * 50
    query = "Python async function definition"
    start = time.perf_counter()
    scores = reranker.predict([[query, d] for d in docs])
    rerank_time = (time.perf_counter() - start) * 1000
    throughput = len(docs) / (rerank_time / 1000)

    print(f"  Rerank (50 docs): {rerank_time:.1f}ms")
    print(f"  Throughput: {throughput:.0f} docs/sec")
    results["bge_rerank"] = {
        "model": "BAAI/bge-reranker-base",
        "load_ms": load_time,
        "rerank_ms": rerank_time,
        "throughput": throughput,
    }

    # Calculate estimated latencies
    vector_search_ms = 5  # pgvector is fast
    total_latency = vector_search_ms + rerank_time
    print(f"\n{'='*60}")
    print("ESTIMATED LATENCY BREAKDOWN")
    print(f"{'='*60}")
    print(f"  Vector search (pgvector): ~{vector_search_ms}ms")
    print(f"  Rerank (50 candidates):   ~{rerank_time:.0f}ms")
    print(f"  Total recall time:        ~{total_latency:.0f}ms")

    results["estimated_latency"] = {
        "vector_search_ms": vector_search_ms,
        "rerank_ms": rerank_time,
        "total_ms": total_latency,
    }

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Auto-configure embedding performance based on hardware"
    )
    parser.add_argument("--benchmark", action="store_true", help="Run benchmarks")
    parser.add_argument("--config", action="store_true", help="Show current config")
    parser.add_argument("--apply", action="store_true", help="Apply config to .env")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Detect hardware
    config = detect_hardware()

    if args.json:
        print(json.dumps(asdict(config), indent=2))
        return

    if args.benchmark:
        results = run_benchmarks(config.device)

        # Save results
        output_file = Path.home() / ".claude" / "cache" / "embedding_benchmark.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "timestamp": datetime.now().isoformat(),
            "device": config.device,
            "gpu": config.gpu_name,
            "config": asdict(config),
            "benchmark": results,
        }
        output_file.write_text(json.dumps(output, indent=2))
        print(f"\nResults saved to: {output_file}")
        return

    if args.config or args.apply:
        print(f"\n{'='*60}")
        print("HARDWARE CONFIGURATION")
        print(f"{'='*60}")
        print(f"  Device:              {config.device}")
        print(f"  GPU:                 {config.gpu_name}")
        print(f"  VRAM:                {config.vram_gb:.1f}GB")
        print()
        print(f"  Embedding batch:     {config.embedding_batch_size}")
        print(f"  Reranker batch:      {config.reranker_batch_size}")
        print(f"  Rerank cache:        {'Enabled' if config.enable_rerank_cache else 'Disabled'}")
        print(f"  Rerank threshold:    {config.rerank_threshold}")
        print(f"  Prewarm models:      {'Yes' if config.prewarm_models else 'No'}")

        if args.apply:
            # Update .env file
            env_file = Path.home() / ".claude" / ".env"
            if env_file.exists():
                content = env_file.read_text()

                updates = {
                    "EMBEDDING_DEVICE": config.device,
                    "EMBEDDING_BATCH_SIZE": str(config.embedding_batch_size),
                    "RERANKER_BATCH_SIZE": str(config.reranker_batch_size),
                    "RERANK_CACHE_ENABLED": str(config.enable_rerank_cache).lower(),
                    "RERANK_THRESHOLD": str(config.rerank_threshold),
                    "PREWARM_MODELS": str(config.prewarm_models).lower(),
                }

                for key, value in updates.items():
                    if f"{key}=" in content:
                        content = content.replace(
                            f"{key}=...",
                            f"{key}={value}"
                        )
                    else:
                        content += f"\n{key}={value}"

                env_file.write_text(content)
                print(f"\nApplied config to: {env_file}")
            else:
                print(f"\n.env file not found: {env_file}")

        return

    # Default: show hardware detection
    print(f"\nDetected Hardware:")
    print(f"  Device:  {config.device}")
    print(f"  GPU:     {config.gpu_name}")
    print(f"  VRAM:    {config.vram_gb:.1f}GB")
    print()
    print("Optimal Settings:")
    print(f"  Embedding batch size:  {config.embedding_batch_size}")
    print(f"  Reranker batch size:   {config.reranker_batch_size}")
    print(f"  Rerank cache:          {'Enabled' if config.enable_rerank_cache else 'Disabled'}")
    print(f"  Rerank threshold:      {config.rerank_threshold}")
    print()
    print("Run with:")
    print("  --benchmark  Run performance benchmarks")
    print("  --config     Show current configuration")
    print("  --apply      Apply config to ~/.claude/.env")


if __name__ == "__main__":
    main()
