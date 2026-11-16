---
name: rp-cli
description: RepoPrompt CLI - codebase exploration with AI-powered file selection
allowed-tools: [Bash, Read]
---

# RepoPrompt CLI Skill

## Mental Model (READ THIS FIRST)

rp-cli has THREE phases - use them in order:

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: EXPLORE (pick ONE)                                 │
│                                                             │
│ Option A: AI-powered (comprehensive, 30s-5min)              │
│   rp-cli -e 'builder "understand the auth system"'          │
│   → AI selects relevant files, populates your selection     │
│                                                             │
│ Option B: Manual (direct, instant)                          │
│   rp-cli -e 'tree'                    # see structure       │
│   rp-cli -e 'search "auth"'           # find files          │
│   rp-cli -e 'structure src/auth/'     # get signatures      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: REFINE (curate what you need)                      │
│                                                             │
│   rp-cli -e 'select set src/auth/ --codemap'  # signatures  │
│   rp-cli -e 'select add src/auth/login.ts'    # full file   │
│   rp-cli -e 'select remove tests/'            # exclude     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: RETRIEVE (get the context)                         │
│                                                             │
│   rp-cli -e 'context'                 # get everything      │
│   rp-cli -e 'read src/auth/login.ts'  # specific file       │
└─────────────────────────────────────────────────────────────┘
```

## When to Use What

| Task | Best Tool | Why |
|------|-----------|-----|
| Complex question about unfamiliar code | `builder --response-type question` | AI explores comprehensively AND answers |
| Architectural understanding | `builder --response-type plan` | AI synthesizes across many files |
| Discovery: "what handles X?" | `builder` (clarify mode) | AI selects relevant files intelligently |
| Known file path | `read` | Direct access, no exploration needed |
| Code signatures overview | `structure` | Signatures without content |
| Pattern matching | `search` | Grep-like results |

## Builder: The AI Exploration Agent

**An intelligent agent that explores your codebase (runs 30s-5min).**

Builder is powerful for complex questions because it:
- Analyzes your task semantically
- Selects relevant files across the entire codebase
- Provides codemaps (signatures) for context
- Can answer questions or generate plans directly

```bash
# Mode 1: CLARIFY (default) - Returns context package for YOU to use
rp-cli -e 'builder "understand auth system"'
# Returns: file selection + codemaps + prompt
# Use when: You want to explore further yourself

# Mode 2: QUESTION - Builder answers your question directly
rp-cli -e 'builder "how does the hook system work" --response-type question'
# Returns: Comprehensive answer based on selected context
# Use when: You want a direct answer to a complex question

# Mode 3: PLAN - Builder creates implementation plan
rp-cli -e 'builder "add checkpoint system for agents" --response-type plan'
# Returns: Step-by-step plan with file references
# Use when: You need architectural guidance
```

**When to use builder:**
- Complex questions requiring understanding multiple systems
- Architectural planning and design
- When you don't know which files are relevant
- When you need comprehensive synthesis

## Token-Efficient Commands

| Command | Token Cost | Use For |
|---------|------------|---------|
| `structure <path>` | ~80% reduction | Code signatures only |
| `read <file> --start-line N --limit M` | Slice only | Specific line ranges |
| `select add <path> --codemap` | Signatures | Add without full content |
| `search` | Matches only | Find patterns |

## Quick Reference

```bash
# PHASE 1: Explore
rp-cli -e 'tree'                          # File tree
rp-cli -e 'tree --folders'                # Folders only
rp-cli -e 'structure src/'                # Code signatures
rp-cli -e 'search "pattern" --context-lines 2'

# PHASE 2: Select (curate context)
rp-cli -e 'select set src/ --codemap'     # Signatures only
rp-cli -e 'select add src/main.ts'        # Full file
rp-cli -e 'select get'                    # View selection
rp-cli -e 'select clear'                  # Reset

# PHASE 3: Retrieve
rp-cli -e 'context'                       # Everything selected
rp-cli -e 'read src/main.ts'              # One file
rp-cli -e 'read src/main.ts --start-line 50 --limit 30'

# AI-powered exploration (comprehensive, 30s-5min)
rp-cli -e 'builder "task"'                           # Context only (clarify)
rp-cli -e 'builder "question" --response-type question'  # Get answer
rp-cli -e 'builder "task" --response-type plan'      # Get plan
```

## Chaining Commands

```bash
# Explore → Select → Retrieve in one line
rp-cli -e 'select set src/auth/ --codemap && select add src/auth/main.ts && context'
```

## Common Mistakes

❌ Using `builder` in clarify mode then not reading the files it selected
✅ After `builder` clarify, use `read` on key files OR use `--response-type question` to get direct answer

❌ Using manual exploration for complex multi-system questions
✅ Use `builder --response-type question` or `--response-type plan` for comprehensive answers

❌ Not using `--response-type` flag when you want an answer
✅ Default is `clarify` (context only) - use `question` or `plan` to get direct output

❌ Skipping the select phase after manual exploration
✅ Use `select` to curate before `context`

## Workflow Examples

### Example 1: Complex Architectural Question (Use Builder)
```bash
# For complex questions spanning multiple systems, use builder with response-type
rp-cli -e 'builder "design a checkpoint system for multi-agent swarms that integrates with hooks and the coordination database" --response-type plan'

# Builder will:
# 1. Explore the entire codebase (30s-5min)
# 2. Select relevant files intelligently
# 3. Generate a comprehensive implementation plan
```

### Example 2: Understanding How Something Works (Builder Question)
```bash
# Get a direct answer to a complex question
rp-cli -e 'builder "how does the hook system work and what events are available" --response-type question'

# Builder explores and synthesizes an answer from multiple files
```

### Example 3: Exploration Then Deep Dive (Builder Clarify + Read)
```bash
# Phase 1: Let builder find relevant files
rp-cli -e 'builder "understand the continuity ledger pattern"'
# Returns: file selection + codemaps (no answer yet)

# Phase 2: Read the key files builder identified
rp-cli -e 'read thoughts/ledgers/CONTINUITY_CLAUDE-example.md'
rp-cli -e 'read .claude/hooks/src/session-start-continuity.ts'

# Phase 3: Now YOU synthesize the answer
```

### Example 4: Quick Known-Location Lookup (Manual)
```bash
# When you already know where to look, skip builder
rp-cli -e 'structure scripts/agentica/patterns/'
rp-cli -e 'read scripts/agentica/PATTERNS.md'
```

## Note

Requires RepoPrompt app running with MCP Server enabled.
Use `rp-cli -d <command>` for detailed help on any command.
