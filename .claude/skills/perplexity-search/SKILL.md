---
name: perplexity-search
description: AI-powered web search, research, and reasoning via Perplexity
allowed-tools: [Bash, Read]
---

# Perplexity AI Search

Web search with AI-powered answers, deep research, and chain-of-thought reasoning.

## When to Use

- Direct web search for ranked results (no AI synthesis)
- AI-synthesized research with citations
- Chain-of-thought reasoning for complex decisions
- Deep comprehensive research on topics

## Models (2025)

| Model | Purpose |
|-------|---------|
| `sonar` | Lightweight search with grounding |
| `sonar-pro` | Advanced search for complex queries |
| `sonar-reasoning-pro` | Chain of thought reasoning |
| `sonar-deep-research` | Expert-level exhaustive research |

## Usage

### Quick question (AI answer)
```bash
uv run python scripts/perplexity_search.py \
    --ask "What is the latest version of Python?"
```

### Direct web search (ranked results, no AI)
```bash
uv run python scripts/perplexity_search.py \
    --search "SQLite graph database patterns" \
    --max-results 5 \
    --recency week
```

### AI-synthesized research
```bash
uv run python scripts/perplexity_search.py \
    --research "compare FastAPI vs Django for microservices"
```

### Chain-of-thought reasoning
```bash
uv run python scripts/perplexity_search.py \
    --reason "should I use Neo4j or SQLite for small graph under 10k nodes?"
```

### Deep comprehensive research
```bash
uv run python scripts/perplexity_search.py \
    --deep "state of AI agent observability 2025"
```

## Parameters

| Parameter | Description |
|-----------|-------------|
| `--ask` | Quick question with AI answer (sonar) |
| `--search` | Direct web search - ranked results without AI synthesis |
| `--research` | AI-synthesized research (sonar-pro) |
| `--reason` | Chain-of-thought reasoning (sonar-reasoning-pro) |
| `--deep` | Deep comprehensive research (sonar-deep-research) |

### Search-specific options
| Parameter | Description |
|-----------|-------------|
| `--max-results N` | Number of results (1-20, default: 10) |
| `--recency` | Filter: `day`, `week`, `month`, `year` |
| `--domains` | Limit to specific domains |

## Mode Selection Guide

| Need | Use | Why |
|------|-----|-----|
| Quick fact | `--ask` | Fast, lightweight |
| Find sources | `--search` | Raw results, no AI overhead |
| Synthesized answer | `--research` | AI combines multiple sources |
| Complex decision | `--reason` | Chain-of-thought analysis |
| Comprehensive report | `--deep` | Exhaustive multi-source research |

## Examples

```bash
# Find recent sources on a topic
uv run python scripts/perplexity_search.py \
    --search "OpenTelemetry AI agent tracing" \
    --recency month --max-results 5

# Get AI synthesis
uv run python scripts/perplexity_search.py \
    --research "best practices for AI agent logging 2025"

# Make a decision
uv run python scripts/perplexity_search.py \
    --reason "microservices vs monolith for startup MVP"

# Deep dive
uv run python scripts/perplexity_search.py \
    --deep "comprehensive guide to building feedback loops for autonomous agents"
```

## API Key Required

Requires `PERPLEXITY_API_KEY` in environment or `~/.claude/.env`.
