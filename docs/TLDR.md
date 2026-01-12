# TLDR: Code Analysis That Actually Fits In Context

**The Core Insight:** LLMs can't read your entire codebase. So we extract the structure, trace the dependencies, and give them exactly what they need—at **95% fewer tokens** than raw code.

Stop burning context windows. Start shipping features.

---

## The Problem: Context Window Bankruptcy

Your codebase is 100,000 lines. Claude can read ~200,000 tokens. Math says you're already in trouble.

| Approach | Tokens | What You Get |
|----------|--------|--------------|
| Read raw files | 23,314 | Full code, zero context window left |
| Grep results | ~5,000 | File paths. No understanding. |
| **TLDR summaries** | **1,189** | Structure + call graph + complexity—everything needed to edit correctly |

**Measured with tiktoken on real codebases.** TLDR gives you 95% token savings while preserving the information LLMs actually need to write correct code.

---

## Quick Start: 30 Seconds to Better Context

```bash
# Install
pip install tldr-code

# Index your project (builds all analysis layers)
tldr warm /path/to/project

# Get LLM-ready context for a function
tldr context process_data --project /path/to/project
```

That's it. The daemon auto-starts and keeps indexes in memory for instant queries.

---

## What Makes TLDR Different

### 1. Behavioral Search, Not Text Search

**The old way:** Search for `authentication` → find variable names, comments, log messages.

**TLDR semantic search:** Understands what code *does*, not just what it says.

```bash
tldr semantic "validate JWT tokens and check expiration" /path/to/project
```

Finds functions by behavior because **every function is embedded with:**
- **L1:** Signature + docstring
- **L2:** What it calls + who calls it (forward & backward call graph)
- **L3:** Complexity metrics (branches, loops, cyclomatic complexity)
- **L4:** Data flow (which variables are used, how they transform)
- **L5:** Dependencies (imports, external modules)
- **Plus:** First ~10 lines of code

This gets encoded into **1024-dimensional embeddings** via `bge-large-en-v1.5`, so semantic search finds `verify_access_token()` even when you ask about JWT validation.

#### Why Both Forward AND Backward Call Graphs?

```python
# Forward (calls): What does login() do?
def login(user, password):
    hash_password(password)  # <-- calls this
    create_session(user)     # <-- and this

# Backward (called_by): What breaks if we change hash_password()?
hash_password()  # <-- called by: login, reset_password, register
```

TLDR indexes **both directions** so you can:
- Trace execution flow (forward: "what does this call?")
- Impact analysis (backward: "what calls this?")

Both are embedded together, so semantic search like `"password hashing"` finds relevant functions whether they *perform* hashing or *use* hashing.

#### No Filtering: Everything Gets Indexed

Unlike traditional tools that skip "trivial" functions, TLDR indexes **every function, method, and class**—including getters, one-liners, and utilities. Why?

Because LLMs need to understand your entire API surface, not just the "important" parts. And token-efficient summaries make this practical.

---

### 2. The 5-Layer Architecture: Different Questions, Different Depths

Not every question needs a full CFG analysis. Pick the layer that matches your task:

```
Layer 5: PDG (Program Dependence) → "What affects this line?"
Layer 4: DFG (Data Flow)          → "Where does this value come from?"
Layer 3: CFG (Control Flow)       → "How complex is this function?"
Layer 2: Call Graph               → "Who calls this?"
Layer 1: AST (Structure)          → "What functions exist?"
```

#### Real Example: Debugging a Null Reference

**Question:** "Why is `user` null on line 42?"

```bash
# L5 (PDG): Program slice - show ONLY code that affects line 42
tldr slice src/auth.py login 42
```

**Output:** 6 lines (out of 150 in the function) that actually matter:
```python
3:   user = db.get_user(username)
7:   if user is None:
12:      raise NotFound
28:  token = create_token(user)  # <-- BUG: skipped null check
35:  session.token = token
42:  return session
```

**Before TLDR:** Read 150-line function, trace logic manually, miss the bug.
**With TLDR:** See exactly the execution path, spot the missing null check at line 28.

---

### 3. Daemon Mode: 300x Faster Than CLI Spawns

**The problem with traditional tooling:** Every query spawns a new process, parses the entire codebase, throws away the results.

**TLDR's daemon:** Long-running background process with indexes in RAM.

| Method | Query Time | What Happens |
|--------|------------|--------------|
| CLI spawn | ~30 seconds | Parse entire codebase, build indexes, analyze, return result, exit |
| Daemon query | ~100ms | Read from in-memory index, return result |
| **Speedup** | **300x** | Measured on a 50-file Python project |

#### How It Works

```bash
# First query auto-starts daemon (transparent)
tldr context login --project .

# Daemon stays running, queries use in-memory indexes
tldr impact login .          # 100ms, not 30s
tldr cfg src/auth.py login   # <10ms if cached
```

**Per-project isolation:** Each project gets its own daemon via deterministic socket names:
```bash
/tmp/tldr-{md5(project_path)[:8]}.sock
```

No cross-contamination. Work on 5 projects simultaneously without conflicts.

**Auto-lifecycle management:**
- Starts on first query
- Auto-shuts down after 5 minutes idle
- Restarts on next query (loads from `.tldr/cache/`)

---

### 4. Salsa-Style Incremental Recomputation

**The insight:** When you edit one function, you don't need to re-analyze the entire codebase.

TLDR uses **content-hash-based caching** with automatic dependency tracking:

```python
# You edit auth.py
# TLDR invalidates:
#   - auth.py's AST cache ✓
#   - Functions that CALL auth functions ✓
#   - Call graph edges involving auth.py ✓
# TLDR keeps:
#   - All other files' analysis ✓
#   - Unchanged functions in auth.py ✓
```

#### Before/After: The `tldr warm` Command

```bash
# First run: Full index build
tldr warm /path/to/project
# → Parses 342 files, builds call graph (5-10 seconds)

# You edit 2 files

# Second run: Incremental update
tldr warm /path/to/project
# → Re-parses 2 files, patches call graph (<1 second)
```

**Measured speedup:** 10x for incremental updates vs full rebuild.

---

### 5. Multi-Language Support (Same API)

Tree-sitter parsers under the hood mean **one interface, 16 languages:**

| Language | AST | Call Graph | CFG | DFG | PDG | Semantic |
|----------|-----|------------|-----|-----|-----|----------|
| Python | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TypeScript | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| JavaScript | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Go | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Rust | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Java | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C++ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ruby | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| PHP | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| C# | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kotlin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Scala | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Swift | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Lua | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Elixir | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

```bash
# Same commands, different languages
tldr context main --project ./go-service --lang go
tldr impact processRequest ./rust-api --lang rust
```

---

## Layer Deep-Dive: What Each One Gives You

### Layer 1: AST (Abstract Syntax Tree) - "What exists?"

**Question:** "What functions are in this file?"

**Token cost:** ~500 tokens for a 500-line file (vs 4,000 raw)

```bash
tldr extract src/auth.py
```

**Output:**
```json
{
  "functions": [
    {
      "name": "login",
      "signature": "def login(username: str, password: str) -> User",
      "params": ["username: str", "password: str"],
      "return_type": "User",
      "is_async": false,
      "line": 42
    }
  ],
  "classes": [
    {
      "name": "AuthService",
      "methods": ["login", "logout", "refresh_token"],
      "line": 12
    }
  ],
  "imports": ["from models import User", "import hashlib"]
}
```

**Use case:** Get a file overview without reading it. See what APIs it exposes.

---

### Layer 2: Call Graph - "Who calls what?"

**Token cost:** +440 tokens (cumulative ~940)

#### Forward Calls: What Does This Function Do?

```bash
tldr calls /path/to/project  # Build call graph
```

```json
{
  "function": "login",
  "calls": [
    "db.get_user",
    "hash_password",
    "create_session",
    "send_welcome_email"
  ]
}
```

#### Backward Calls: Impact Analysis Before Refactoring

```bash
# "If I change hash_password(), what breaks?"
tldr impact hash_password /path/to/project
```

```json
{
  "function": "hash_password",
  "called_by": [
    {"file": "auth.py", "function": "login", "line": 47},
    {"file": "auth.py", "function": "reset_password", "line": 89},
    {"file": "registration.py", "function": "register", "line": 23},
    {"file": "tests/test_auth.py", "function": "test_login", "line": 15}
  ]
}
```

**Use case:** Safe refactoring. Know exactly what depends on what.

---

### Layer 3: CFG (Control Flow Graph) - "How complex is this?"

**Token cost:** +110 tokens (cumulative ~1,050)

```bash
tldr cfg src/auth.py login
```

**Output:**
```json
{
  "function": "login",
  "blocks": [
    {"id": 0, "statements": ["user = db.get_user(username)"]},
    {"id": 1, "statements": ["if user is None:", "    raise NotFound"]},
    {"id": 2, "statements": ["if not verify_password(...):", "    raise AuthError"]},
    {"id": 3, "statements": ["session = create_session(user)", "return session"]}
  ],
  "edges": [[0,1], [1,2], [2,3], [1,3], [2,3]],
  "complexity": 3
}
```

**What you learn:**
- **Complexity: 3** → This function has 3 decision points (2 if statements = 3 paths)
- **Blocks:** 4 basic blocks (straight-line code between branches)
- **Edges:** Shows which blocks can follow which (for tracing execution)

**Use case:** Find overly complex functions that need refactoring (complexity > 10 = code smell).

---

### Layer 4: DFG (Data Flow Graph) - "Where does this value come from?"

**Token cost:** +130 tokens (cumulative ~1,180)

```bash
tldr dfg src/auth.py login
```

**Output:**
```json
{
  "function": "login",
  "variables": [
    {"name": "user", "defined_at": [3], "used_at": [5, 8, 15]},
    {"name": "token", "defined_at": [12], "used_at": [18]},
    {"name": "session", "defined_at": [15], "used_at": [18]}
  ],
  "flows": [
    {"from": "username", "to": "user", "via": "db.get_user"},
    {"from": "user", "to": "session", "via": "create_session"},
    {"from": "session", "to": "token", "via": "session.token"}
  ]
}
```

**Use case:** Debugging. "Why is `token` wrong? Let me trace back through the data flow."

---

### Layer 5: PDG (Program Dependence Graph) - "What affects this line?"

**Token cost:** +150 tokens (cumulative ~1,330)

**The killer feature for debugging:** Program slicing.

```bash
# "What code affects the return value on line 42?"
tldr slice src/auth.py login 42
```

**Output:**
```json
{
  "target_line": 42,
  "slice": [3, 5, 12, 28, 35, 42],
  "slice_code": [
    "user = db.get_user(username)",
    "if user is None: raise NotFound",
    "if not verify_password(password, user.hash): raise AuthError",
    "token = create_token(user)",
    "session.token = token",
    "return session"
  ]
}
```

**Before TLDR:** Read 150-line function, manually trace dependencies.
**With TLDR:** See only the 6 lines that actually matter.

**Use case:** Answering "why did this variable have this value?" in complex functions.

---

## Semantic Search: Find Code by Behavior

Traditional search finds syntax. TLDR semantic search finds behavior.

### The Architecture

1. **Extract all functions** (no filtering—getters, utilities, everything)
2. **Build rich embeddings** from all 5 layers:
   ```
   Function: validate_token
   Signature: def validate_token(token: str, secret: str) -> dict
   Description: Verify JWT token signature and check expiration
   Calls: jwt.decode, check_expiration, get_user_claims
   Called by: authenticate_request, refresh_session
   Control flow: complexity 4, 6 basic blocks
   Data flow: 8 variables, token → decoded → claims
   Dependencies: import jwt, from datetime import datetime
   Code:
       decoded = jwt.decode(token, secret, algorithms=['HS256'])
       if decoded['exp'] < time.time():
           raise TokenExpired
       ...
   ```

3. **Encode with bge-large-en-v1.5** → 1024-dimensional vector
4. **FAISS index** for fast similarity search

### Example Queries

```bash
# Find authentication code
tldr semantic "verify user credentials and create session" .

# Find error handling
tldr semantic "catch exceptions and log errors" .

# Find database operations
tldr semantic "query postgres with SQL and parse results" .
```

**Why it works:** The embedding includes:
- What the function does (docstring)
- What it calls (behavior inference)
- Who calls it (usage patterns)
- How complex it is (implementation hints)
- What it imports (technology stack)

So searching for `"JWT validation"` finds functions that call `jwt.decode`, are called by `authenticate_*` functions, and import `jwt`—even if they're named `verify_access_token`.

### Build the Index

```bash
# One-time index build
tldr warm /path/to/project  # Builds semantic index automatically

# Query (uses daemon, ~100ms)
tldr semantic "your natural language query" /path/to/project
```

Results include file path, function name, line number, and similarity score.

---

## Daemon Architecture: Why It's Fast

### The Old Way (Every CLI Tool)

```
You: tldr context login
CLI: Fork process → Parse codebase → Build AST → Build call graph → Return result → Exit
Time: 30 seconds

You: tldr impact login  (2 minutes later)
CLI: Fork process → Parse codebase → Build AST → Build call graph → Return result → Exit
Time: 30 seconds (ALL OVER AGAIN)
```

### The TLDR Way

```
You: tldr context login
Daemon: Auto-starts if not running → Loads indexes into RAM → Returns result
Time: 100ms

You: tldr impact login  (2 minutes later)
Daemon: Reads from in-memory index → Returns result
Time: 50ms

You: (nothing for 5 minutes)
Daemon: Auto-shuts down, writes state to .tldr/cache/
```

### Daemon Lifecycle

| Event | What Happens |
|-------|--------------|
| First query | Hook auto-starts daemon, indexes load into RAM |
| Subsequent queries | Daemon serves from memory (100ms) |
| File edit | Daemon detects change, incrementally updates affected indexes |
| 5min idle | Daemon auto-shuts down to save resources |
| Next query | Daemon restarts, loads from cache (still faster than parsing) |

### Per-Project Isolation

```bash
# Project A
cd ~/myproject
tldr context main
# → Daemon socket: /tmp/tldr-a3f2c8d1.sock

# Project B (different terminal)
cd ~/otherproject
tldr context main
# → Daemon socket: /tmp/tldr-b9e4d7f3.sock
```

Socket path = `md5(absolute_path)[:8]`, so projects never interfere.

### Daemon Commands

```bash
# Manual control (usually automatic)
tldr daemon start --project .    # Start daemon
tldr daemon stop --project .     # Graceful shutdown
tldr daemon status --project .   # Check health

# Example output
$ tldr daemon status --project .
Daemon running (PID: 42315)
Socket: /tmp/tldr-a3f2c8d1.sock
Uptime: 127 seconds
Files indexed: 342
Cache hits: 89.3%
Semantic index: 1,247 functions
```

### Available Daemon Commands

| Command | Purpose | Latency |
|---------|---------|---------|
| `ping` | Health check | <1ms |
| `status` | Stats (uptime, cache hits, files) | <1ms |
| `search` | Pattern search in code | ~50ms |
| `extract` | Full file analysis (AST) | ~10ms |
| `impact` | Reverse call graph | ~20ms |
| `dead` | Dead code detection | ~100ms |
| `arch` | Architecture layers | ~150ms |
| `cfg` | Control flow graph | ~15ms |
| `dfg` | Data flow graph | ~20ms |
| `slice` | Program slicing | ~30ms |
| `calls` | Cross-file call graph | ~80ms |
| `semantic` | Embedding-based search | ~100ms |
| `tree` | File tree structure | ~20ms |
| `structure` | Code structure (codemaps) | ~30ms |
| `context` | LLM-ready context | ~50ms |
| `imports` | Parse file imports | ~10ms |
| `importers` | Reverse import lookup | ~100ms |

Compare to **30 seconds** per CLI spawn.

---

## Integration with Claude Code

TLDR integrates via TypeScript hooks that query the daemon for zero-overhead code understanding:

| Hook | Triggers On | TLDR Operation |
|------|-------------|----------------|
| `session-start-tldr-cache` | Session start | Auto-start daemon, warm indexes |
| `session-start-dead-code` | Session start | Detect unreachable functions |
| `tldr-context-inject` | Before Task/Read | Inject function context into prompt |
| `smart-search-router` | Before Grep | Use TLDR pattern search instead |
| `edit-context-inject` | Before Edit | Extract file structure for safer edits |
| `signature-helper` | Before Edit | Find function signatures in scope |
| `arch-context-inject` | Before Task | Inject architecture layer info |
| `post-edit-diagnostics` | After Edit/Write | **Shift-left validation** - catch type errors immediately |

### Hook Implementation Pattern

```typescript
// .claude/hooks/src/any-hook.ts
import { queryDaemonSync } from './daemon-client.js';

// Query daemon (100ms, in-memory indexes)
const result = queryDaemonSync(projectDir, {
  cmd: 'dead',
  language: 'python'
});

// Fallback: If daemon not running, client auto-spawns CLI
```

**Result:** Claude gets code understanding automatically, without manual commands, without 30-second waits.

### Shift-Left Validation

The `post-edit-diagnostics` hook enables **shift-left validation**—catching type errors at edit time, not test time.

**Traditional flow:**
```
Edit → Run tests → Tests fail → "Oh, type error" → Fix → Run tests again
       └─────────────────── 30-60 seconds wasted ───────────────────┘
```

**With shift-left:**
```
Edit → [hook: diagnostics] → "Type error line 42" → Fix immediately
       └── 200ms ──┘
```

**Why it matters:**
- Type errors are deterministic—no need to "test" them
- Pyright catches errors tests miss (unreachable code, wrong types in unexecuted paths)
- Faster iteration = more attempts per session = better results

The hook is **silent when everything's fine**. Only speaks up when there's a problem worth mentioning.

---

## CLI Reference

### Core Commands

```bash
# Project setup
tldr warm [path]                      # Build/update all indexes (incremental)

# Structure exploration
tldr tree [path]                       # File tree
tldr structure [path] --lang python    # Code structure overview
tldr extract <file>                    # Detailed file analysis (L1)

# Search
tldr search <pattern> [path]           # Text search in code
tldr semantic <query> [path]           # Behavioral semantic search

# LLM context
tldr context <entry> --project . --depth 2  # Get LLM-ready context
```

### Analysis Commands

```bash
# Call graph
tldr calls [path]                      # Build cross-file call graph
tldr impact <function> [path]          # Who calls this function?

# Control flow
tldr cfg <file> <function>             # Control flow graph + complexity

# Data flow
tldr dfg <file> <function>             # Variable definitions and uses

# Program slicing
tldr slice <file> <func> <line>        # What affects this line?
```

### Codebase Analysis

```bash
tldr dead [path] --entry main cli      # Find unreachable code
tldr arch [path]                       # Detect architecture layers
tldr imports <file>                    # Parse imports from a file
tldr importers <module> [path]         # Find all files that import a module
tldr diagnostics <file|path>           # Type check + lint (pyright/ruff)
tldr change-impact [files...]          # Find tests affected by changes
tldr doctor                            # Check/install diagnostic tools
```

### Diagnostic Tool Setup

```bash
# Check which type checkers/linters are installed
tldr doctor
# → Shows installed ✓ and missing ✗ tools per language

# Install missing tools for a language
tldr doctor --install python   # Installs pyright + ruff
tldr doctor --install go       # Installs golangci-lint
```

### Import Analysis

Track dependency relationships across your codebase:

```bash
# What does this file import?
tldr imports src/auth.py
# → [{"module": "jwt", "names": ["encode", "decode"], ...}, ...]

# Who imports this module? (reverse import lookup)
tldr importers validate_input src/
# → {"module": "validate_input", "importers": [{"file": "api/routes.py", ...}, ...]}
```

This complements `tldr impact` which tracks function *calls*—`tldr importers` tracks *imports*.

### Diagnostics (Type Check + Lint)

```bash
# Single file
tldr diagnostics src/auth.py

# Whole project
tldr diagnostics . --project

# Human-readable output
tldr diagnostics src/ --format text
# → Found 2 errors, 5 warnings
# → E src/auth.py:45:12: Expected int, got str [reportArgumentType]

# Type check only (skip linter)
tldr diagnostics src/ --no-lint
```

Wraps language-specific type checkers and linters:

| Language | Type Checker | Linter |
|----------|--------------|--------|
| Python | pyright | ruff |
| TypeScript | tsc | - |
| Go | go vet | golangci-lint |
| Rust | cargo check | clippy |
| Java | javac | checkstyle |
| C/C++ | gcc/clang | cppcheck |
| Ruby | - | rubocop |
| PHP | - | phpstan |
| Kotlin | kotlinc | ktlint |
| Swift | swiftc | swiftlint |
| C# | dotnet build | - |
| Scala | scalac | - |
| Elixir | mix compile | credo |

Tools are optional - if not installed, silently skipped.

### Change Impact (Selective Testing)

```bash
# Auto-detect changed files (session dirty flags, then git)
tldr change-impact
# → {"affected_tests": ["tests/test_auth.py"], "skipped_count": 247, ...}

# Explicit files
tldr change-impact src/auth.py src/session.py

# Session-modified files only
tldr change-impact --session

# Git diff
tldr change-impact --git --git-base HEAD~3

# Actually run the affected tests
tldr change-impact --run
```

Uses call graph + import analysis to find which tests are affected by code changes. Run only what matters instead of the full suite.

### Daemon Management

```bash
tldr daemon start --project .          # Start daemon manually
tldr daemon stop --project .           # Stop daemon
tldr daemon status --project .         # Check daemon health
```

---

## Python API

```python
from tldr.api import (
    # Layer 1: AST
    extract_functions,
    extract_file,
    get_imports,

    # Layer 2: Call Graph
    get_call_graph,
    build_function_index,

    # Layer 3: CFG
    get_cfg_context,
    get_cfg_blocks,

    # Layer 4: DFG
    get_dfg_context,

    # Layer 5: PDG
    get_slice,

    # Unified
    get_relevant_context,
)

# Example: Get multi-layer context for a function
context = get_relevant_context(
    entry_point="process_data",
    project_path="./src",
    depth=2,
    layers=["ast", "call_graph", "cfg"]
)

print(context)  # LLM-ready text with structure + call graph + complexity
```

---

## Performance Numbers (Measured)

### Daemon Speedup: 155x Faster

**What we measured:** Time to complete identical queries via (a) spawning `tldr` CLI vs (b) querying the daemon via Unix socket.

| Command | Daemon | CLI | Speedup |
|---------|--------|-----|---------|
| `search` | 0.2ms | 72ms | **302x** |
| `extract` | 9ms | 97ms | **11x** |
| `impact` | 0.2ms | 1,129ms | **7,374x** |
| `tree` | 0.3ms | 76ms | **217x** |
| `structure` | 0.6ms | 181ms | **285x** |
| **Total** | **10ms** | **1,555ms** | **155x** |

**Why `impact` shows 7,374x speedup:** The CLI must rebuild the entire call graph from scratch on every invocation (~1.1 seconds). The daemon keeps the call graph in memory, so queries return in <1ms. This is the primary value proposition of the daemon architecture.

#### Methodology

```bash
# Benchmark script: opc/scripts/benchmark_daemon.py
# Hardware: MacBook Pro M1 Max, 64GB RAM
# Project: tldr-code (26 Python files, ~5,000 lines)
# Protocol:
#   1. Start daemon, let it fully index
#   2. Warm up: Run each query once (not counted)
#   3. Measure: 10 iterations per query, record mean ± stdev
#   4. CLI: Fresh `tldr <cmd>` process each time
#   5. Daemon: Unix socket query to running daemon
```

**Reproduce it yourself:**
```bash
cd opc/packages/tldr-code
source .venv/bin/activate
tldr daemon start --project .
python /path/to/opc/scripts/benchmark_daemon.py
```

---

### Token Savings: 89% Reduction

**What we measured:** Tokens required to understand code at different granularities, comparing raw file reads vs TLDR structured output.

| Scenario | Raw Tokens | TLDR Tokens | Savings |
|----------|------------|-------------|---------|
| Single file analysis | 9,114 | 7,074 | 22% |
| Function + callees | 21,271 | 175 | **99%** |
| Codebase overview (26 files) | 103,901 | 11,664 | 89% |
| Deep call chain (7 files) | 53,474 | 2,667 | 95% |
| **Total** | **187,760** | **21,580** | **89%** |

#### What Each Scenario Measures

1. **Single file analysis (22% savings)**
   - Raw: `cat api.py` → 9,114 tokens
   - TLDR: `tldr extract api.py` → 7,074 tokens
   - *Note: Modest savings because extract includes full file structure. Better use case is when you need overview, not full code.*

2. **Function + callees (99% savings)** ← The killer feature
   - Raw: Read 3 files that contain the function and everything it calls → 21,271 tokens
   - TLDR: `tldr context extract_file --depth 2` → 175 tokens
   - *Why so dramatic:* TLDR's call graph navigates directly to relevant code. You don't read irrelevant functions in those files.

3. **Codebase overview (89% savings)**
   - Raw: Read all 26 Python files → 103,901 tokens
   - TLDR: `tldr structure . --lang python` → 11,664 tokens
   - *Trade-off:* You get function signatures and structure, not full implementations.

4. **Deep call chain (95% savings)**
   - Raw: Read 7 files in the call chain → 53,474 tokens
   - TLDR: `tldr context get_relevant_context --depth 3` → 2,667 tokens
   - *Same principle as #2, deeper traversal.*

#### Methodology

```bash
# Benchmark script: opc/scripts/benchmark_tokens.py
# Token counter: tiktoken with cl100k_base encoding (Claude's tokenizer)
# Project: tldr-code source (tldr/*.py)
# Protocol:
#   1. "Raw" = cat file(s) and count tokens
#   2. "TLDR" = run tldr command and count output tokens
#   3. No cherry-picking: same files for each scenario
```

**Important caveats:**
- "Raw" assumes reading entire files. In practice, you might grep + read specific sections, which would be somewhere between raw and TLDR.
- Scenarios are chosen to represent real use cases (understanding a function, getting codebase overview), not to maximize savings.
- The 99% savings on "function context" is real but represents the best case (call graph navigation).

**Reproduce it yourself:**
```bash
cd opc/packages/tldr-code
source .venv/bin/activate
uv pip install tiktoken  # if not installed
python /path/to/opc/scripts/benchmark_tokens.py
```

---

### Summary

| Metric | Before TLDR | After TLDR | Improvement |
|--------|-------------|------------|-------------|
| Query latency | 1.5s | 10ms | **155x faster** |
| Tokens for function context | 21K | 175 | **99% savings** |
| Tokens for codebase overview | 104K | 12K | **89% savings** |

**Cost impact:** At Claude Sonnet rates (~$3/M input tokens), saving 166K tokens per session = ~$0.50/session. Over 1,000 sessions, that's $500.

---

### Legacy Numbers (Reference)

These are older measurements on different projects, kept for reference:

| File Size | Raw Tokens | TLDR Tokens | Savings |
|-----------|------------|-------------|---------|
| 500-line Python | ~4,000 | ~200 | 95% |
| 1000-line TypeScript | ~8,000 | ~400 | 95% |
| 10-file context | ~40,000 | ~2,000 | 95% |

| Operation | CLI Spawn | Daemon (Cold) | Daemon (Cached) |
|-----------|-----------|---------------|-----------------|
| `extract <file>` | ~50ms | ~10ms | ~2ms |
| `impact <func>` | ~100ms | ~20ms | <1ms |
| `search <pattern>` | 2-5s | ~100ms | ~50ms |

---

## Cache Structure

TLDR stores all indexes in `.tldr/cache/`:

```
.tldr/
├── daemon.pid               # Running daemon PID
├── status                   # "ready" | "indexing" | "stale"
└── cache/
    ├── call_graph.json      # Forward call edges
    ├── file_hashes.json     # Content hashes (dirty detection)
    ├── parse_cache/         # Cached AST results per file
    │   ├── src_auth.py.json
    │   └── src_db.py.json
    └── semantic/            # Embedding-based search
        ├── index.faiss      # FAISS vector index
        └── metadata.json    # Function metadata for results
```

### Incremental Updates

```bash
# First run: Full index
tldr warm .
# → Parses 342 files, builds call graph (8 seconds)

# Edit 2 files

# Second run: Incremental
tldr warm .
# → Detects 2 changed files via content hash
# → Re-parses only those 2 files
# → Patches call graph edges
# → Updates semantic index for changed functions
# (0.7 seconds)
```

**How dirty detection works:**
1. Compute SHA256 hash of each file's content
2. Store in `file_hashes.json`
3. On next `warm`, compare hashes
4. Re-parse only files with changed hashes
5. Update call graph edges for changed functions

---

## Architecture Decisions: Why These Choices?

### Why Tree-sitter?

- **10-100x faster** than language-native parsers (Python's `ast`, TypeScript's `tsc`)
- **Incremental parsing**: Re-parse only edited portions of files
- **Multi-language**: Same API for Python, TS, Go, Rust, JS
- **Error-tolerant**: Parses incomplete/broken code (handles in-progress edits)

### Why JSON Output?

- **LLM-friendly**: Can be pasted directly into prompts
- **Language-agnostic**: Works with any tooling
- **Human-readable**: Easy to debug and inspect
- **Transformable**: Pipe through `jq` for filtering

### Why Layered Architecture?

Different questions need different analysis depths:

| Question | Layer | Why |
|----------|-------|-----|
| "What functions exist?" | L1 (AST) | Fast, lightweight |
| "Who calls this?" | L2 (Call Graph) | Need cross-file analysis |
| "Is this function complex?" | L3 (CFG) | Need branching logic |
| "Where does this variable come from?" | L4 (DFG) | Need data dependencies |
| "What affects this line?" | L5 (PDG) | Need full dependency graph |

**Pay for what you need.** Don't compute CFGs when you just need function names.

### Why a Daemon?

- **Speed**: Eliminate 30s CLI spawn overhead → 100ms daemon query
- **Memory efficiency**: Load indexes once, reuse for all queries
- **Caching**: Memoization persists across queries
- **Zero config**: Auto-starts, auto-stops, transparent to users

### Why Semantic Search?

Because **text search finds syntax, not behavior.**

```bash
# Text search
tldr search "JWT"  # Finds: comments, variable names, log messages

# Semantic search
tldr semantic "validate JWT tokens"  # Finds: functions that actually validate JWTs
```

Embeddings encode:
- What the function does (docstring)
- What it calls (behavior)
- Who calls it (usage)
- Data flow patterns
- Complexity

So you find code by *what it does*, not just *what it says*.

---

## Real-World Workflows

### Debugging a Bug

```bash
# 1. Find where the error occurs
tldr search "raise AuthError" src/

# 2. Get the program slice (what code leads to that line?)
tldr slice src/auth.py validate_token 47

# 3. Find all callers (who might trigger this error?)
tldr impact validate_token src/

# 4. Check data flow (where does the bad value come from?)
tldr dfg src/auth.py validate_token
```

**Before TLDR:** Read 5 files (2,000 lines), trace logic manually, guess.
**With TLDR:** Targeted analysis in 4 commands, see exactly what matters.

---

### Before Refactoring

```bash
# 1. Understand current implementation
tldr extract src/utils.py
tldr cfg src/utils.py process_data

# 2. Find all usages (impact analysis)
tldr impact process_data src/

# 3. Check architectural role
tldr arch src/

# 4. Look for dead code to remove
tldr dead src/ --entry main cli
```

**Result:** Confidence to refactor without breaking callers.

---

### Understanding a New Codebase

```bash
# 1. Get overview
tldr tree src/
tldr structure src/ --lang python

# 2. Find entry points
tldr arch src/  # Shows entry/middle/leaf layers

# 3. Trace from entry to implementation
tldr context main --project src/ --depth 3

# 4. Find relevant code semantically
tldr semantic "database queries" src/
```

**Before TLDR:** Read README, grep around, read random files, build mental model.
**With TLDR:** Structured exploration in minutes, not hours.

---

### Adding a Feature

```bash
# 1. Find similar existing code
tldr semantic "user authentication and session management" .

# 2. Understand how it works
tldr context login --project . --depth 2

# 3. Check what depends on it
tldr impact login .

# 4. Find where to add new code
tldr arch src/  # See layer structure
```

**Result:** Implement features in the right place, following existing patterns.

---

## Installation

```bash
# From the local fork (opc/packages/llm-tldr)
cd opc/packages/llm-tldr
pip install -e .

# With all language support
pip install -e ".[all]"

# Or from PyPI (upstream)
pip install llm-tldr
```

### Related Projects

- **[llm-tldr](https://github.com/parcadei/llm-tldr)**: Original implementation by parcadei. Our fork is at `opc/packages/llm-tldr` for local development and customization.

### Dependencies

```bash
# Core
pip install tree-sitter tree-sitter-languages

# Semantic search (optional)
pip install sentence-transformers faiss-cpu

# Language-specific parsers
pip install tree-sitter-python tree-sitter-typescript
pip install tree-sitter-javascript tree-sitter-go tree-sitter-rust
```

---

## What's Next?

- **VSCode extension**: Inline TLDR analysis while editing
- **Git integration**: Track complexity over time, highlight risky changes
- **Custom embeddings**: Fine-tune on your codebase's domain
- **Streaming daemon**: Live updates as you type
- **Multi-language call graphs**: Trace Python → TypeScript API calls

---

## License

Apache 2.0

---

## Why "TLDR"?

Because codebases are **Too Long; Didn't Read**—but LLMs still need to understand them.

TLDR extracts the structure, traces the dependencies, measures the complexity, and gives LLMs exactly what they need to write correct code.

At 95% fewer tokens than raw files.

**Ship features. Don't read documentation.**
