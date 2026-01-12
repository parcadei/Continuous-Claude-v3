#!/usr/bin/env python3
"""
Store Learning with Structured Logging

Example integration showing:
- Storage operation timing
- Deduplication results (skip/match)
- Backend selection
- Embedding generation
- Metadata validation

Run with:
    uv run python scripts/core/store_learning_logged.py \
        --session-id "abc123" \
        --type "WORKING_SOLUTION" \
        --content "Pattern X works well for Y"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from scripts.core.logging_config import (
    get_logger,
    setup_logging,
    generate_correlation_id,
    get_correlation_logger,
)

# Load .env
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()

project_dir = os.environ.get("CLAUDE_PROJECT_DIR", str(Path(__file__).parent.parent.parent))
sys.path.insert(0, project_dir)


# =============================================================================
# Logger Setup
# =============================================================================

logger = get_logger("store_learning", "store_learning")

# Valid types and confidence levels
LEARNING_TYPES = [
    "FAILED_APPROACH", "WORKING_SOLUTION", "USER_PREFERENCE",
    "CODEBASE_PATTERN", "ARCHITECTURAL_DECISION", "ERROR_FIX", "OPEN_THREAD",
]
CONFIDENCE_LEVELS = ["high", "medium", "low"]
DEDUP_THRESHOLD = 0.85


# =============================================================================
# Logging Wrappers
# =============================================================================

def log_storage_start(
    session_id: str,
    learning_type: str | None,
    correlation_id: str,
) -> None:
    """Log storage operation start."""
    logger.info(
        "Storage operation started",
        trace_id=correlation_id,
        operation="storage_start",
        session_id=session_id,
        learning_type=learning_type or "legacy",
    )


def log_backend_selection(backend: str, correlation_id: str) -> None:
    """Log which backend was selected."""
    logger.info(
        "Backend selected for storage",
        trace_id=correlation_id,
        operation="backend_selection",
        backend=backend,
    )


def log_embedding_generation(
    provider: str,
    dimension: int,
    correlation_id: str,
    duration_ms: float,
) -> None:
    """Log embedding generation details."""
    logger.debug(
        "Embedding generated",
        trace_id=correlation_id,
        operation="embedding_generation",
        provider=provider,
        dimension=dimension,
        duration_ms=round(duration_ms, 2),
    )


def log_deduplication_check(
    correlation_id: str,
    similarity_threshold: float,
) -> None:
    """Log deduplication check start."""
    logger.debug(
        "Deduplication check started",
        trace_id=correlation_id,
        operation="deduplication_check",
        similarity_threshold=similarity_threshold,
    )


def log_deduplication_result(
    is_duplicate: bool,
    existing_id: str | None,
    similarity: float,
    correlation_id: str,
) -> None:
    """Log deduplication result."""
    if is_duplicate:
        logger.info(
            "Learning skipped - duplicate detected",
            trace_id=correlation_id,
            operation="deduplication_result",
            duplicate=True,
            existing_id=existing_id,
            similarity=round(similarity, 4),
        )
    else:
        logger.debug(
            "Deduplication passed - no match found",
            trace_id=correlation_id,
            operation="deduplication_result",
            duplicate=False,
        )


def log_metadata_validation(
    correlation_id: str,
    has_type: bool,
    has_context: bool,
    has_tags: bool,
    has_confidence: bool,
    content_length: int,
) -> None:
    """Log metadata validation results."""
    logger.debug(
        "Metadata validated",
        trace_id=correlation_id,
        operation="metadata_validation",
        has_type=has_type,
        has_context=has_context,
        has_tags=has_tags,
        has_confidence=has_confidence,
        content_length=content_length,
    )


def log_storage_complete(
    memory_id: str,
    backend: str,
    correlation_id: str,
    duration_ms: float,
    skipped: bool = False,
    skip_reason: str | None = None,
) -> None:
    """Log storage operation completion."""
    logger.info(
        "Storage operation completed",
        trace_id=correlation_id,
        operation="storage_complete",
        memory_id=memory_id,
        backend=backend,
        duration_ms=round(duration_ms, 2),
        skipped=skipped,
        skip_reason=skip_reason,
    )


def log_error(
    error_type: str,
    error_message: str,
    correlation_id: str,
    operation: str = "unknown",
) -> None:
    """Log error with context."""
    logger.error(
        f"Error during {operation}",
        trace_id=correlation_id,
        operation=operation,
        error_type=error_type,
        error_message=error_message,
    )


# =============================================================================
# Storage Functions with Logging
# =============================================================================

async def store_learning_v2(
    session_id: str,
    content: str,
    learning_type: str | None = None,
    context: str | None = None,
    tags: list[str] | None = None,
    confidence: str | None = None,
    correlation_id: str = "",
) -> dict:
    """Store learning with v2 schema and comprehensive logging."""
    storage_id = generate_correlation_id()

    log_storage_start(session_id, learning_type, storage_id)

    if not content or not content.strip():
        return {"success": False, "error": "No content provided"}

    # Get backend
    if os.environ.get("DATABASE_URL"):
        backend = "postgres"
    else:
        from scripts.core.db.memory_factory import get_default_backend
        backend = get_default_backend()

    log_backend_selection(backend, storage_id)

    try:
        from scripts.core.db.memory_factory import create_memory_service
        from scripts.core.db.embedding_service import EmbeddingService

        memory = await create_memory_service(
            backend=backend,
            session_id=session_id,
        )

        # Generate embedding
        embed_start = datetime.now(timezone.utc).timestamp()
        embedder = EmbeddingService(provider="local")
        try:
            embedding = await embedder.embed(content)
        finally:
            await embedder.aclose()

        embed_duration_ms = (datetime.now(timezone.utc).timestamp() - embed_start) * 1000
        log_embedding_generation("local", len(embedding), storage_id, embed_duration_ms)

        # Deduplication check
        log_deduplication_check(storage_id, DEDUP_THRESHOLD)

        try:
            existing = await memory.search_vector(embedding, limit=1)
            if existing and len(existing) > 0:
                top_match = existing[0]
                similarity = top_match.get("similarity", 0)
                if similarity >= DEDUP_THRESHOLD:
                    await memory.close()
                    log_deduplication_result(True, top_match.get("id"), similarity, storage_id)
                    return {
                        "success": True,
                        "skipped": True,
                        "reason": f"duplicate (similarity: {similarity:.2f})",
                        "existing_id": top_match.get("id"),
                    }
            log_deduplication_result(False, None, 0.0, storage_id)
        except Exception as e:
            logger.warning(
                "Deduplication check failed, proceeding with storage",
                trace_id=storage_id,
                operation="deduplication_fallback",
                error=str(e),
            )

        # Build metadata
        metadata = {
            "type": "session_learning",
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if learning_type:
            metadata["learning_type"] = learning_type
        if context:
            metadata["context"] = context
        if tags:
            metadata["tags"] = tags
        if confidence:
            metadata["confidence"] = confidence

        log_metadata_validation(
            storage_id,
            has_type=bool(learning_type),
            has_context=bool(context),
            has_tags=bool(tags),
            has_confidence=bool(confidence),
            content_length=len(content),
        )

        # Store
        storage_start = datetime.now(timezone.utc).timestamp()
        memory_id = await memory.store(content, metadata=metadata, embedding=embedding)
        storage_duration_ms = (datetime.now(timezone.utc).timestamp() - storage_start) * 1000

        await memory.close()

        log_storage_complete(
            memory_id,
            backend,
            storage_id,
            storage_duration_ms,
        )

        return {
            "success": True,
            "memory_id": memory_id,
            "backend": backend,
            "content_length": len(content),
            "embedding_dim": len(embedding),
        }

    except Exception as e:
        log_error(type(e).__name__, str(e), storage_id, "store_learning_v2")
        return {"success": False, "error": str(e)}


async def store_learning_legacy(
    session_id: str,
    worked: str,
    failed: str,
    decisions: str,
    patterns: str,
    correlation_id: str = "",
) -> dict:
    """Legacy storage with logging."""
    storage_id = correlation_id or generate_correlation_id()

    log_storage_start(session_id, "legacy", storage_id)

    # Build learning content
    learning_parts = []
    if worked and worked.lower() != "none":
        learning_parts.append(f"What worked: {worked}")
    if failed and failed.lower() != "none":
        learning_parts.append(f"What failed: {failed}")
    if decisions and decisions.lower() != "none":
        learning_parts.append(f"Decisions: {decisions}")
    if patterns and patterns.lower() != "none":
        learning_parts.append(f"Patterns: {patterns}")

    if not learning_parts:
        return {"success": False, "error": "No learning content provided"}

    learning_content = "\n".join(learning_parts)

    # Build metadata
    metadata = {
        "type": "session_learning",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "categories": {
            "worked": bool(worked and worked.lower() != "none"),
            "failed": bool(failed and failed.lower() != "none"),
            "decisions": bool(decisions and decisions.lower() != "none"),
            "patterns": bool(patterns and patterns.lower() != "none"),
        }
    }

    # Get backend
    if os.environ.get("DATABASE_URL"):
        backend = "postgres"
    else:
        from scripts.core.db.memory_factory import get_default_backend
        backend = get_default_backend()

    log_backend_selection(backend, storage_id)

    try:
        from scripts.core.db.memory_factory import create_memory_service
        from scripts.core.db.embedding_service import EmbeddingService

        memory = await create_memory_service(
            backend=backend,
            session_id=session_id,
        )

        embed_start = datetime.now(timezone.utc).timestamp()
        embedder = EmbeddingService(provider="local")
        try:
            embedding = await embedder.embed(learning_content)
        finally:
            await embedder.aclose()

        embed_duration_ms = (datetime.now(timezone.utc).timestamp() - embed_start) * 1000
        log_embedding_generation("local", len(embedding), storage_id, embed_duration_ms)

        storage_start = datetime.now(timezone.utc).timestamp()
        memory_id = await memory.store(learning_content, metadata=metadata, embedding=embedding)
        storage_duration_ms = (datetime.now(timezone.utc).timestamp() - storage_start) * 1000

        await memory.close()

        log_storage_complete(memory_id, backend, storage_id, storage_duration_ms)

        return {
            "success": True,
            "memory_id": memory_id,
            "backend": backend,
            "content_length": len(learning_content),
            "embedding_dim": len(embedding),
        }

    except Exception as e:
        log_error(type(e).__name__, str(e), storage_id, "store_learning_legacy")
        return {"success": False, "error": str(e)}


# =============================================================================
# Main Entry
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Store learning with structured logging")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--worked", default="None")
    parser.add_argument("--failed", default="None")
    parser.add_argument("--decisions", default="None")
    parser.add_argument("--patterns", default="None")
    parser.add_argument("--type", choices=LEARNING_TYPES)
    parser.add_argument("--content")
    parser.add_argument("--context")
    parser.add_argument("--tags")
    parser.add_argument("--confidence", choices=CONFIDENCE_LEVELS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    setup_logging(script_name="store_learning", log_level="INFO")

    correlation_id = generate_correlation_id()

    if args.content:
        tags = None
        if args.tags:
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]

        result = await store_learning_v2(
            session_id=args.session_id,
            content=args.content,
            learning_type=args.type,
            context=args.context,
            tags=tags,
            confidence=args.confidence,
            correlation_id=correlation_id,
        )
    else:
        result = await store_learning_legacy(
            session_id=args.session_id,
            worked=args.worked,
            failed=args.failed,
            decisions=args.decisions,
            patterns=args.patterns,
            correlation_id=correlation_id,
        )

    if args.json:
        print(json.dumps(result))
    else:
        if result.get("skipped"):
            print(f"~ Learning skipped: {result.get('reason', 'duplicate')}")
        elif result["success"]:
            print(f"Learning stored (id: {result.get('memory_id', 'unknown')})")
            print(f"  Backend: {result.get('backend', 'unknown')}")
            print(f"  Content: {result.get('content_length', 0)} chars")
        else:
            print(f"Failed to store learning: {result.get('error', 'unknown')}")
            sys.exit(1)

    return 0


if __name__ == "__main__":
    setup_logging(script_name="store_learning", log_level="INFO")
    sys.exit(asyncio.run(main()))
