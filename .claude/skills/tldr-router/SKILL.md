---
name: tldr-router
description: Maps questions to the optimal tldr command for code analysis
allowed-tools: [Bash, Read]
---

# TLDR Smart Router

Maps questions to the optimal tldr command. Use this to pick the right layer.

## Question → Command Mapping

### "What files/functions exist?"
```bash
tldr tree . --ext .py          # File overview
tldr structure src/ --lang python  # Function/class overview
```
**Use:** Starting exploration, orientation

### "What does X call / who calls X?"
```bash
tldr context <function> --project . --depth 2
tldr calls src/
```
**Use:** Understanding architecture, finding entry points

### "How complex is X?"
```bash
tldr cfg <file> <function>
```
**Use:** Identifying refactoring candidates, understanding difficulty

### "Where does variable Y come from?"
```bash
tldr dfg <file> <function>
```
**Use:** Debugging, understanding data flow

### "What affects line Z?"
```bash
tldr slice <file> <function> <line>
```
**Use:** Impact analysis, safe refactoring

### "Search for pattern P"
```bash
tldr search "pattern" src/
```
**Use:** Finding code, structural search

## Decision Tree

```
START
  │
  ├─► "What exists?" ──► tree / structure
  │
  ├─► "How does X connect?" ──► context / calls
  │
  ├─► "Why is X complex?" ──► cfg
  │
  ├─► "Where does Y flow?" ──► dfg
  │
  ├─► "What depends on Z?" ──► slice
  │
  └─► "Find something" ──► search
```

## Intent Detection Keywords

| Intent | Keywords | Layer |
|--------|----------|-------|
| Navigation | "what", "where", "find", "exists" | tree, structure, search |
| Architecture | "calls", "uses", "connects", "depends" | context, calls |
| Complexity | "complex", "refactor", "branches", "paths" | cfg |
| Data Flow | "variable", "value", "assigned", "comes from" | dfg |
| Impact | "affects", "changes", "slice", "dependencies" | slice/pdg |
| Debug | "bug", "error", "investigate", "broken" | cfg + dfg + context |

## Automatic Hook Integration

The `tldr-read-enforcer` and `tldr-context-inject` hooks automatically:
1. Detect intent from your messages
2. Route to appropriate layers
3. Inject context into tool calls

You don't need to manually run these commands - the hooks do it for you.

## Manual Override

If you need a specific layer the hooks didn't provide:

```bash
# Force specific analysis
tldr cfg path/to/file.py function_name
tldr dfg path/to/file.py function_name
tldr slice path/to/file.py function_name 42
```
