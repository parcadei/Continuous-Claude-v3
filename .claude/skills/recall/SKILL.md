---
name: recall
description: Semantic memory retrieval - query temporal facts with embedding search and optional reranking
allowed-tools: [Bash, Read]
---

# Recall Skill

Retrieve relevant facts from temporal memory using semantic search (pgvector) with optional reranking.

## When to Use

- Searching past session facts by meaning, not exact text
- Finding relevant context for current task
- Recalling decisions, outcomes, or learnings from past work
- When you need semantic similarity, not keyword matching

## Workflow

```
Query -> Embed (Voyage/Local) -> Vector Search (pgvector) -> Rerank (Cohere/CrossEncoder) -> Return
```

## CLI Commands

### Simple Recall (Vector Search Only)

```bash
# Basic recall - top 5 similar facts
uv run python scripts/recall_temporal_facts.py --query "authentication implementation"

# Adjust result count
uv run python scripts/recall_temporal_facts.py --query "database schema changes" --k 10

# Use local embeddings (no API key needed)
uv run python scripts/recall_temporal_facts.py --query "error handling patterns" --provider local
```

### Reranked Recall (Higher Precision)

```bash
# Add reranking for better precision (uses Cohere by default)
uv run python scripts/recall_temporal_facts.py --query "authentication" --rerank

# Use local cross-encoder reranker (no API key)
uv run python scripts/recall_temporal_facts.py --query "authentication" --rerank --rerank-provider local

# Custom session ID
uv run python scripts/recall_temporal_facts.py --query "test failures" --session-id abc123
```

## Providers

### Embedding Providers (--provider)

| Provider | Model | Dimension | Requires |
|----------|-------|-----------|----------|
| `voyage` (default) | voyage-3 | 1024 | VOYAGE_API_KEY |
| `local` | all-MiniLM-L6-v2 | 384 | sentence-transformers |

### Rerank Providers (--rerank-provider)

| Provider | Model | Requires |
|----------|-------|----------|
| `cohere` (default) | rerank-english-v3.0 | COHERE_API_KEY |
| `local` | ms-marco-MiniLM-L-12-v2 | sentence-transformers |

## Example Output

```
Recalling facts for: "authentication implementation"
Session: current-session-id
Provider: voyage, Rerank: cohere

Found 5 matching facts:

1. [0.89] auth_method: oauth2_pkce
   Confidence: 0.95, Similarity: 0.92

2. [0.85] auth_provider: auth0
   Confidence: 0.90, Similarity: 0.88

3. [0.82] session_storage: redis
   Confidence: 0.85, Similarity: 0.84
```

## Environment Variables

- `VOYAGE_API_KEY` - For Voyage embeddings
- `COHERE_API_KEY` - For Cohere reranking
- `DATABASE_URL` - PostgreSQL connection (defaults to localhost)

## Related

- `scripts/agentica_patterns/embedding_service.py` - Embedding providers
- `scripts/agentica_patterns/reranker.py` - Reranking implementations
- `scripts/temporal_memory/store_pg.py` - PostgreSQL temporal store
