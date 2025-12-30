---
name: exa-search
description: Web search and code documentation via Exa AI (built-in MCP tools)
---

# Exa AI Search

Real-time web search and code documentation retrieval via built-in Exa MCP tools.

## When to Use

- Web search for current information
- Code documentation and API examples
- Library/SDK usage patterns
- Fetching content from specific URLs

## Available Tools

### `mcp__exa__web_search_exa`
Real-time web search with live crawling.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query (required) |
| `numResults` | number | Results to return (default: 8) |
| `livecrawl` | string | `"fallback"` or `"preferred"` (default: fallback) |
| `contextMaxCharacters` | number | Max context chars for LLMs (default: 10000) |
| `type` | string | `"auto"`, `"fast"`, or `"deep"` (default: auto) |

### `mcp__exa__get_code_context_exa`
Code-specific search for APIs, libraries, and SDKs.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query (required) |
| `tokensNum` | number | Tokens to return (1000-50000, default: 5000) |

## Usage Examples

### Web search
```
Use mcp__exa__web_search_exa with:
- query: "FastAPI dependency injection patterns 2025"
- numResults: 5
- type: "auto"
```

### Fetch URL content
```
Use mcp__exa__web_search_exa with:
- query: "site:docs.python.org asyncio"
- livecrawl: "preferred"
```

### Code documentation
```
Use mcp__exa__get_code_context_exa with:
- query: "React useState hook examples"
- tokensNum: 8000
```

### Library API lookup
```
Use mcp__exa__get_code_context_exa with:
- query: "Pydantic v2 field validators"
- tokensNum: 10000
```

## Mode Selection Guide

| Need | Use | Why |
|------|-----|-----|
| General web search | `web_search_exa` | Fast, real-time results |
| Fetch specific URL | `web_search_exa` with `livecrawl: preferred` | Live content retrieval |
| Code examples | `get_code_context_exa` | Optimized for code patterns |
| API documentation | `get_code_context_exa` | Fresh library docs |
| Current events | `web_search_exa` with `type: deep` | Comprehensive coverage |

## Comparison to Previous Tools

| Old Tool | Exa Replacement |
|----------|-----------------|
| Firecrawl scrape | `web_search_exa` with `livecrawl: preferred` |
| Firecrawl search | `web_search_exa` |
| Perplexity search | `web_search_exa` |
| Perplexity (code) | `get_code_context_exa` |

## Notes

- Exa tools are built-in to Claude Code (no API key required)
- No script wrapper needed - call tools directly
- Results are optimized for LLM context windows
- Use `get_code_context_exa` for programming-related queries
