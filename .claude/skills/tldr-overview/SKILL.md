---
name: tldr-overview
description: Get a token-efficient overview of any project using the TLDR stack
allowed-tools: [Bash, Read]
---

# TLDR Project Overview

Get a token-efficient overview of any project using the TLDR stack.

## Trigger
- `/overview` or `/tldr-overview`
- "give me an overview of this project"
- "what's in this codebase"
- Starting work on an unfamiliar project

## Execution

### 1. File Tree (Navigation Map)
```bash
tldr tree . --ext .py    # or .ts, .go, .rs
```

### 2. Code Structure (What Exists)
```bash
tldr structure src/ --lang python --max 50
```
Returns: functions, classes, imports per file

### 3. Call Graph Entry Points (Architecture)
```bash
tldr calls src/
```
Returns: cross-file relationships, main entry points

### 4. Key Function Complexity (Hot Spots)
For each entry point found:
```bash
tldr cfg src/main.py main  # Get complexity
```

## Output Format

```
## Project Overview: {project_name}

### Structure
{tree output - files and directories}

### Key Components
{structure output - functions, classes per file}

### Architecture (Call Graph)
{calls output - how components connect}

### Complexity Hot Spots
{cfg output - functions with high cyclomatic complexity}

---
Token cost: ~{N} tokens (vs ~{M} raw = {savings}% savings)
```

## When NOT to Use
- Already familiar with the project
- Working on a specific file (use targeted tldr commands instead)
- Test files (need full context)

## Programmatic Usage

```python
from tldr.api import get_file_tree, get_code_structure, build_project_call_graph

# 1. Tree
tree = get_file_tree("src/", extensions={".py"})

# 2. Structure
structure = get_code_structure("src/", language="python", max_results=50)

# 3. Call graph
calls = build_project_call_graph("src/", language="python")

# 4. Complexity for hot functions
for edge in calls.edges[:10]:
    cfg = get_cfg_context("src/" + edge[0], edge[1])
```
