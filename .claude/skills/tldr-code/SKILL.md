---
name: tldr-code
description: Token-efficient code analysis via 5-layer stack (AST, Call Graph, CFG, DFG, PDG). 95% token savings.
allowed-tools: [Bash]
keywords: [debug, refactor, understand, complexity, "call graph", "data flow", "what calls", "how complex", search, explore, analyze, dead code, architecture, imports]
---

# TLDR-Code: Complete Reference

Token-efficient code analysis. **95% savings** vs raw file reads.

## Quick Reference

| Task | Command |
|------|---------|
| File tree | `tldr tree src/` |
| Code structure | `tldr structure . --lang python` |
| Search code | `tldr search "pattern" .` |
| Call graph | `tldr calls src/` |
| Who calls X? | `tldr impact func_name .` |
| Control flow | `tldr cfg file.py func` |
| Data flow | `tldr dfg file.py func` |
| Program slice | `tldr slice file.py func 42` |
| Dead code | `tldr dead src/` |
| Architecture | `tldr arch src/` |
| Imports | `tldr imports file.py` |
| Who imports X? | `tldr importers module_name .` |
| Affected tests | `tldr change-impact --git` |
| Type check | `tldr diagnostics file.py` |
| Semantic search | `tldr semantic search "auth flow"` |

---

## The 5-Layer Stack

```
Layer 1: AST         ~500 tokens   Function signatures, imports
Layer 2: Call Graph  +440 tokens   What calls what (cross-file)
Layer 3: CFG         +110 tokens   Complexity, branches, loops
Layer 4: DFG         +130 tokens   Variable definitions/uses
Layer 5: PDG         +150 tokens   Dependencies, slicing
───────────────────────────────────────────────────────────────
Total:              ~1,200 tokens  vs 23,000 raw = 95% savings
```

---

## CLI Commands

### Navigation

```bash
# File tree
tldr tree [path]
tldr tree src/ --ext .py .ts        # Filter extensions
tldr tree . --show-hidden           # Include hidden files

# Code structure (codemaps)
tldr structure [path] --lang python
tldr structure src/ --max 100       # Max files to analyze
```

### Search

```bash
# Text search
tldr search <pattern> [path]
tldr search "def process" src/
tldr search "class.*Error" . --ext .py
tldr search "TODO" . -C 3           # 3 lines context
tldr search "func" . --max 50       # Limit results

# Semantic search (natural language)
tldr semantic search "authentication flow"
tldr semantic search "error handling" --k 10
tldr semantic search "database queries" --expand  # Include call graph
```

### File Analysis

```bash
# Full file info
tldr extract <file>
tldr extract src/api.py
tldr extract src/api.py --class UserService      # Filter to class
tldr extract src/api.py --function process       # Filter to function
tldr extract src/api.py --method UserService.get # Filter to method

# Relevant context (follows call graph)
tldr context <entry> --project <path>
tldr context main --project src/ --depth 3
tldr context UserService.create --project . --lang typescript
```

### Flow Analysis

```bash
# Control flow graph (complexity)
tldr cfg <file> <function>
tldr cfg src/processor.py process_data
# Returns: cyclomatic complexity, blocks, branches, loops

# Data flow graph (variable tracking)
tldr dfg <file> <function>
tldr dfg src/processor.py process_data
# Returns: where variables are defined, read, modified

# Program slice (what affects line X)
tldr slice <file> <function> <line>
tldr slice src/processor.py process_data 42
tldr slice src/processor.py process_data 42 --direction forward
tldr slice src/processor.py process_data 42 --var result
```

### Codebase Analysis

```bash
# Build cross-file call graph
tldr calls [path]
tldr calls src/ --lang python

# Reverse call graph (who calls this function?)
tldr impact <func> [path]
tldr impact process_data src/ --depth 5
tldr impact authenticate . --file auth  # Filter by file

# Find dead/unreachable code
tldr dead [path]
tldr dead src/ --entry main cli test_  # Specify entry points
tldr dead . --lang typescript

# Detect architectural layers
tldr arch [path]
tldr arch src/ --lang python
# Returns: entry layer, middle layer, leaf layer, circular deps
```

### Import Analysis

```bash
# Parse imports from file
tldr imports <file>
tldr imports src/api.py
tldr imports src/api.ts --lang typescript

# Reverse import lookup (who imports this module?)
tldr importers <module> [path]
tldr importers datetime src/
tldr importers UserService . --lang typescript
```

### Quality & Testing

```bash
# Type check + lint
tldr diagnostics <file|path>
tldr diagnostics src/api.py
tldr diagnostics . --project              # Whole project
tldr diagnostics src/ --no-lint           # Type check only
tldr diagnostics src/ --format text       # Human-readable

# Find affected tests
tldr change-impact [files...]
tldr change-impact                        # Auto-detect (session/git)
tldr change-impact src/api.py             # Explicit files
tldr change-impact --session              # Session-modified files
tldr change-impact --git                  # Git diff files
tldr change-impact --git --git-base main  # Diff against branch
tldr change-impact --run                  # Actually run affected tests
```

### Caching

```bash
# Pre-build call graph cache
tldr warm <path>
tldr warm src/ --lang python
tldr warm . --background                  # Build in background

# Build semantic index (one-time)
tldr semantic index [path]
tldr semantic index . --lang python
tldr semantic index . --model all-MiniLM-L6-v2  # Smaller model (80MB)
```

---

## Daemon (Faster Queries)

The daemon holds indexes in memory for instant repeated queries.

### Daemon Commands

```bash
# Start daemon (backgrounds automatically)
tldr daemon start
tldr daemon start --project /path/to/project

# Check status
tldr daemon status

# Stop daemon
tldr daemon stop

# Send raw command
tldr daemon query ping
tldr daemon query status

# Notify file change (for hooks)
tldr daemon notify <file>
tldr daemon notify src/api.py
```

### Daemon Features

| Feature | Description |
|---------|-------------|
| Auto-shutdown | 30 minutes idle |
| Query caching | SalsaDB memoization |
| Content hashing | Skip unchanged files |
| Dirty tracking | Incremental re-indexing |
| Cross-platform | Unix sockets / Windows TCP |

### Daemon Socket Protocol

Send JSON to socket, receive JSON response:

```json
// Request
{"cmd": "search", "pattern": "process", "max_results": 10}

// Response
{"status": "ok", "results": [...]}
```

**All 22 daemon commands:**
```
ping, status, shutdown, search, extract, impact, dead, arch,
cfg, dfg, slice, calls, warm, semantic, tree, structure,
context, imports, importers, notify, diagnostics, change_impact
```

---

## Semantic Search (P6)

Natural language code search using embeddings.

### Setup

```bash
# Build index (downloads model on first run)
tldr semantic index .

# Default model: bge-large-en-v1.5 (1.3GB, best quality)
# Smaller model: all-MiniLM-L6-v2 (80MB, faster)
tldr semantic index . --model all-MiniLM-L6-v2
```

### Search

```bash
tldr semantic search "authentication flow"
tldr semantic search "error handling patterns" --k 10
tldr semantic search "database connection" --expand  # Follow call graph
```

### Configuration

In `.claude/settings.json`:
```json
{
  "semantic_search": {
    "enabled": true,
    "auto_reindex_threshold": 20,
    "model": "bge-large-en-v1.5"
  }
}
```

---

## Languages Supported

| Language | AST | Call Graph | CFG | DFG | PDG |
|----------|-----|------------|-----|-----|-----|
| Python | Yes | Yes | Yes | Yes | Yes |
| TypeScript | Yes | Yes | Yes | Yes | Yes |
| JavaScript | Yes | Yes | Yes | Yes | Yes |
| Go | Yes | Yes | Yes | Yes | Yes |
| Rust | Yes | Yes | Yes | Yes | Yes |
| Java | Yes | Yes | - | - | - |
| C/C++ | Yes | Yes | - | - | - |
| Ruby | Yes | - | - | - | - |
| PHP | Yes | - | - | - | - |
| Kotlin | Yes | - | - | - | - |
| Swift | Yes | - | - | - | - |
| C# | Yes | - | - | - | - |
| Scala | Yes | - | - | - | - |
| Lua | Yes | - | - | - | - |
| Elixir | Yes | - | - | - | - |

---

## Ignore Patterns

TLDR respects `.tldrignore` (gitignore syntax):

```gitignore
# .tldrignore
.venv/
__pycache__/
node_modules/
*.min.js
dist/
```

First run creates `.tldrignore` with sensible defaults.
Use `--no-ignore` to bypass.

---

## When to Use TLDR vs Other Tools

| Task | Use TLDR | Use Grep |
|------|----------|----------|
| Find function definition | `tldr extract file --function X` | - |
| Search code patterns | `tldr search "pattern"` | - |
| String literal search | - | `grep "literal"` |
| Config values | - | `grep "KEY="` |
| Cross-file calls | `tldr calls` | - |
| Reverse deps | `tldr impact func` | - |
| Complexity analysis | `tldr cfg file func` | - |
| Variable tracking | `tldr dfg file func` | - |
| Natural language query | `tldr semantic search` | - |

---

## Python API

```python
from tldr.api import (
    # L1: AST
    extract_file, extract_functions, get_imports,
    # L2: Call Graph
    build_project_call_graph, get_intra_file_calls,
    # L3: CFG
    get_cfg_context,
    # L4: DFG
    get_dfg_context,
    # L5: PDG
    get_slice, get_pdg_context,
    # Unified
    get_relevant_context,
    # Analysis
    analyze_dead_code, analyze_architecture, analyze_impact,
)

# Example: Get context for LLM
ctx = get_relevant_context("src/", "main", depth=2, language="python")
print(ctx.to_llm_string())
```

---

## Bug Fixing Workflow (Navigation + Read)

**Key insight:** TLDR navigates, then you read. Don't try to fix bugs from summaries alone.

### The Pattern

```bash
# 1. NAVIGATE: Find which files matter
tldr imports file.py              # What does buggy file depend on?
tldr impact func_name .           # Who calls the buggy function?
tldr calls .                      # Cross-file edges (follow 2-hop for models)

# 2. READ: Get actual code for critical files (2-4 files, not all 50)
# Use Read tool or tldr search -C for code with context
tldr search "def buggy_func" . -C 20
```

### Why This Works

For cross-file bugs (e.g., wrong field name, type mismatch), you need to see:
- The file with the bug (handler accessing `task.user_id`)
- The file with the contract (model defining `owner_id`)

TLDR finds which files matter. Then you read them.

### Getting More Context

If TLDR output isn't enough:
- `tldr search "pattern" . -C 20` - Get actual code with 20 lines context
- `tldr imports file.py` - See what a file depends on
- Read the file directly if you need the full implementation

---

## Token Savings Evidence

```
Raw file read:    23,314 tokens
TLDR all layers:   1,189 tokens
─────────────────────────────────
Savings:              95%
```

The insight: Call graph navigates to relevant code, then layers give structured summaries. You don't read irrelevant code.
