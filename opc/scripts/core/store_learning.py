#!/usr/bin/env python3
"""Store session learnings in PostgreSQL with pgvector embeddings.

Claude-native learning storage - called by stop-learnings hook or memory extractor.
Stores learnings in memory for semantic recall in future sessions.

Usage (legacy):
    uv run python opc/scripts/store_learning.py \
        --session-id "abc123" \
        --worked "Approach X worked well" \
        --failed "Y didn't work" \
        --decisions "Chose Z because..." \
        --patterns "Reusable technique..."

Usage (v2 - direct content):
    uv run python opc/scripts/store_learning.py \
        --session-id "abc123" \
        --type "WORKING_SOLUTION" \
        --context "hook development" \
        --tags "hooks,patterns" \
        --confidence "high" \
        --content "Pattern X works well for Y"

Learning Types:
    FAILED_APPROACH: Things that didn't work
    WORKING_SOLUTION: Successful approaches
    USER_PREFERENCE: User style/preferences
    CODEBASE_PATTERN: Discovered code patterns
    ARCHITECTURAL_DECISION: Design choices made
    ERROR_FIX: Error->solution pairs
    OPEN_THREAD: Unfinished work/TODOs

Environment:
    DATABASE_URL: PostgreSQL connection string
    VOYAGE_API_KEY: For embeddings (optional, falls back to local)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load global ~/.claude/.env first, then local .env
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()

# Add parent directory to path (for imports like 'from db.memory_factory')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Valid learning types for --type parameter
LEARNING_TYPES = [
    "FAILED_APPROACH",
    "WORKING_SOLUTION",
    "USER_PREFERENCE",
    "CODEBASE_PATTERN",
    "ARCHITECTURAL_DECISION",
    "ERROR_FIX",
    "OPEN_THREAD",
]

# Valid confidence levels
CONFIDENCE_LEVELS = ["high", "medium", "low"]

# Deduplication threshold (0.85 = 85% similar)
DEDUP_THRESHOLD = 0.85

# Keywords that indicate GLOBAL scope (cross-project learnings)
GLOBAL_KEYWORDS = {
    "windows", "linux", "macos", "darwin", "posix", "platform",
    "wsl", "mingw", "cygwin", "powershell", "cmd.exe",
    "hooks", "hook", "skill", "skills", "mcp", "claude code",
    "subagent", "agent", "spawn", "memory", "embedding",
    "python", "typescript", "javascript", "rust", "go",
    "async", "await", "promise", "generator", "decorator",
    "git", "npm", "pip", "docker", "kubernetes", "postgres", "redis",
    "segfault", "stack overflow", "memory leak", "race condition",
}

# Keywords that indicate PROJECT scope (project-specific)
PROJECT_KEYWORDS = {
    "src/", "lib/", "app/", "components/", "pages/", "routes/",
    "test/", "tests/", "spec/", "__tests__/",
    "package.json", "tsconfig", "pyproject.toml", "cargo.toml",
}

# Singleton embedding service (prevents 1.5GB model reload per learning)
_embedder = None


def get_embedder():
    """Get or create singleton EmbeddingService instance.

    The BGE embedding model is ~1.5GB. Creating a new instance per learning
    causes OOM after ~10 learnings. This singleton ensures the model is
    loaded once and reused.
    """
    global _embedder
    if _embedder is None:
        from db.embedding_service import EmbeddingService
        _embedder = EmbeddingService(provider="local")
    return _embedder


def get_project_id(project_dir: str | None) -> str | None:
    """Generate stable project ID from absolute path."""
    if not project_dir or not project_dir.strip():
        return None
    import hashlib
    abs_path = str(Path(project_dir).resolve())
    if not abs_path or abs_path == ".":
        return None
    return hashlib.sha256(abs_path.encode()).hexdigest()[:16]


def classify_scope(
    content: str,
    tags: list[str] | None = None,
    context: str | None = None,
) -> str:
    """Classify learning as PROJECT or GLOBAL scope.

    GLOBAL: Cross-project patterns (Windows issues, hooks, language patterns)
    PROJECT: Project-specific code, paths, architecture
    """
    combined = content.lower()
    if context:
        combined += " " + context.lower()
    if tags:
        combined += " " + " ".join(tags).lower()

    global_score = sum(1 for kw in GLOBAL_KEYWORDS if kw in combined)
    project_score = sum(1 for kw in PROJECT_KEYWORDS if kw in combined)

    if global_score > project_score and global_score >= 2:
        return "GLOBAL"
    return "PROJECT"


async def store_learning_v2(
    session_id: str,
    content: str,
    learning_type: str | None = None,
    context: str | None = None,
    tags: list[str] | None = None,
    confidence: str | None = None,
    project_dir: str | None = None,
    scope: str | None = None,
) -> dict:
    """Store learning with v2 metadata schema, deduplication, and scope classification.

    Args:
        session_id: Session identifier
        content: The learning content
        learning_type: One of LEARNING_TYPES (e.g., WORKING_SOLUTION)
        context: What this learning relates to (e.g., "hook development")
        tags: List of tags for categorization
        confidence: Confidence level (high/medium/low)
        project_dir: Project directory for PROJECT scope learnings
        scope: Override scope classification (PROJECT or GLOBAL)

    Returns:
        dict with success status, memory_id, or skipped info for duplicates
    """
    try:
        from db.memory_factory import (
            create_memory_service,
            get_default_backend,
        )
        from db.embedding_service import EmbeddingService
    except ImportError as e:
        return {"success": False, "error": f"Memory service not available: {e}"}

    if not content or not content.strip():
        return {"success": False, "error": "No content provided"}

    # Get backend - prefer postgres if DATABASE_URL is set
    if os.environ.get("DATABASE_URL"):
        backend = "postgres"
    else:
        backend = get_default_backend()

    try:
        memory = await create_memory_service(
            backend=backend,
            session_id=session_id,
        )

        # Generate embedding (uses singleton to avoid 1.5GB model reload)
        embedder = get_embedder()
        embedding = await embedder.embed(content)

        # Deduplication check: search for similar existing memories
        try:
            existing = await memory.search_vector(embedding, limit=1)
            if existing and len(existing) > 0:
                top_match = existing[0]
                similarity = top_match.get("similarity", 0)
                if similarity >= DEDUP_THRESHOLD:
                    await memory.close()
                    return {
                        "success": True,
                        "skipped": True,
                        "reason": f"duplicate (similarity: {similarity:.2f})",
                        "existing_id": top_match.get("id"),
                    }
        except Exception:
            # If search fails, proceed with storing (don't block on dedup errors)
            pass

        # Classify scope if not explicitly provided
        final_scope = scope or classify_scope(content, tags, context)
        project_id = get_project_id(project_dir) if project_dir else None

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

        # Store with embedding, scope, and project_id
        memory_id = await memory.store(
            content,
            metadata=metadata,
            embedding=embedding,
            scope=final_scope,
            project_id=project_id,
        )

        await memory.close()

        return {
            "success": True,
            "memory_id": memory_id,
            "backend": backend,
            "content_length": len(content),
            "embedding_dim": len(embedding),
            "scope": final_scope,
            "project_id": project_id,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def store_learning(
    session_id: str,
    worked: str,
    failed: str,
    decisions: str,
    patterns: str,
) -> dict:
    """Store learning in PostgreSQL with embedding.

    Args:
        session_id: Session identifier
        worked: What worked well
        failed: What failed or was tricky
        decisions: Key decisions made
        patterns: Reusable patterns

    Returns:
        dict with success status and memory_id
    """
    try:
        from db.memory_factory import (
            create_memory_service,
            get_default_backend,
        )
        from db.embedding_service import EmbeddingService
    except ImportError as e:
        return {"success": False, "error": f"Memory service not available: {e}"}

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

    # Metadata for filtering/retrieval
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

    # Get backend - prefer postgres if DATABASE_URL is set
    if os.environ.get("DATABASE_URL"):
        backend = "postgres"
    else:
        backend = get_default_backend()

    try:
        memory = await create_memory_service(
            backend=backend,
            session_id=session_id,
        )

        # Generate embedding (uses singleton to avoid 1.5GB model reload)
        embedder = get_embedder()
        embedding = await embedder.embed(learning_content)

        # Store with embedding for semantic search
        memory_id = await memory.store(
            learning_content,
            metadata=metadata,
            embedding=embedding,
        )

        await memory.close()

        return {
            "success": True,
            "memory_id": memory_id,
            "backend": backend,
            "content_length": len(learning_content),
            "embedding_dim": len(embedding),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="Store session learnings in memory")
    parser.add_argument("--session-id", required=True, help="Session identifier")

    # Legacy parameters (v1)
    parser.add_argument("--worked", default="None", help="What worked well (legacy)")
    parser.add_argument("--failed", default="None", help="What failed or was tricky (legacy)")
    parser.add_argument("--decisions", default="None", help="Key decisions made (legacy)")
    parser.add_argument("--patterns", default="None", help="Reusable patterns (legacy)")

    # New v2 parameters
    parser.add_argument(
        "--type",
        choices=LEARNING_TYPES,
        help="Learning type (v2)",
    )
    parser.add_argument("--content", help="Direct content (v2)")
    parser.add_argument("--context", help="What this relates to (v2)")
    parser.add_argument("--tags", help="Comma-separated tags (v2)")
    parser.add_argument(
        "--confidence",
        choices=CONFIDENCE_LEVELS,
        help="Confidence level (v2)",
    )

    # Scope parameters (v3)
    parser.add_argument("--project-dir", help="Project directory for PROJECT scope")
    parser.add_argument(
        "--scope",
        choices=["PROJECT", "GLOBAL"],
        help="Override scope classification",
    )

    # Output options
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Determine which mode to use: v2 if --content is provided, else legacy
    if args.content:
        # Parse tags from comma-separated string to list
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
            project_dir=args.project_dir,
            scope=args.scope,
        )
    else:
        # Legacy mode
        result = await store_learning(
            session_id=args.session_id,
            worked=args.worked,
            failed=args.failed,
            decisions=args.decisions,
            patterns=args.patterns,
        )

    if args.json:
        # Ensure all values are JSON serializable (UUIDs, etc.)
        def serialize(obj):
            if hasattr(obj, 'hex'):  # UUID
                return str(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        print(json.dumps(result, default=serialize))
    else:
        if result.get("skipped"):
            print(f"~ Learning skipped: {result.get('reason', 'duplicate')}")
        elif result["success"]:
            print(f"Learning stored (id: {result.get('memory_id', 'unknown')})")
            print(f"  Backend: {result.get('backend', 'unknown')}")
            print(f"  Content: {result.get('content_length', 0)} chars")
            if result.get("scope"):
                print(f"  Scope: {result.get('scope')}")
        else:
            print(f"Failed to store learning: {result.get('error', 'unknown')}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
