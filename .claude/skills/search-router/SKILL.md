---
name: search-router
description: Choose the right search tool for each query type
user-invocable: false
---

# Search Tool Router

Use the most token-efficient search tool for each query type.

## When to Use

- Searching for code patterns
- Finding where something is implemented
- Looking for specific identifiers
- Understanding how code works

## Decision Tree

```
Query Type?
├── CODE EXPLORATION (symbols, call chains, data flow)
│   → TLDR Search - 95% token savings
│   DEFAULT FOR ALL CODE SEARCH - use instead of Grep
│   Examples: "spawn_agent", "DataPoller", "redis usage"
│   Command: tldr search "query" .
│
├── STRUCTURAL (AST patterns)
│   → AST-grep (/ast-grep-find) - ~50 tokens output
│   Examples: "def foo", "class Bar", "import X", "@decorator"
│
├── SEMANTIC (conceptual questions)
│   → TLDR Semantic - 5-layer embeddings (P6)
│   Examples: "how does auth work", "find error handling patterns"
│   Command: tldr semantic search "query"
│
├── LITERAL (exact text, regex)
│   → Grep tool - LAST RESORT
│   Only when TLDR/AST-grep don't apply
│   Examples: error messages, config values, non-code text
│
└── FULL CONTEXT (need complete understanding)
    → Read tool - 1500+ tokens
    Last resort after finding the right file
```

## Token Efficiency Comparison

| Tool | Output Size | Best For |
|------|-------------|----------|
| **TLDR** | **~50-500** | **DEFAULT: Code symbols, call graphs, data flow** |
| **TLDR Semantic** | **~100-300** | **Conceptual queries (P6, embedding-based)** |
| AST-grep | ~50 tokens | Function/class definitions, imports, decorators |
| Grep | ~200-2000 | LAST RESORT: Non-code text, regex |
| Read | ~1500+ | Full understanding after finding the file |

## Examples

```bash
# CODE EXPLORATION → TLDR (DEFAULT)
tldr search "spawn_agent" .
tldr search "redis" . --layer call_graph

# STRUCTURAL → AST-grep
/ast-grep-find "async def $FUNC($$$):" --lang python

# SEMANTIC → TLDR Semantic
tldr semantic search "how does authentication work"

# LITERAL → Grep (LAST RESORT - prefer TLDR)
Grep pattern="check_evocation" path=opc/scripts

# FULL CONTEXT → Read (after finding file)
Read file_path=opc/scripts/z3_erotetic.py
```

## Optimal Flow

```
1. AST-grep: "Find async functions" → 3 file:line matches
2. Read: Top match only → Full understanding
3. Skip: 4 irrelevant files → 6000 tokens saved
```

## Related Skills

- `/tldr-search` - **DEFAULT** - Code exploration with 95% token savings
- `/ast-grep-find` - Structural code search
- `/morph-search` - Fast text search
