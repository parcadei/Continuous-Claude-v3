---
name: tldr-deep
description: Full 5-layer analysis of a specific function for debugging or deep understanding
allowed-tools: [Bash, Read]
---

# TLDR Deep Analysis

Full 5-layer analysis of a specific function. Use when debugging or deeply understanding code.

## Trigger
- `/tldr-deep <function_name>`
- "analyze function X in detail"
- "I need to deeply understand how Y works"
- Debugging complex functions

## Layers

| Layer | Purpose | Command |
|-------|---------|---------|
| L1: AST | Structure | `tldr extract <file>` |
| L2: Call Graph | Navigation | `tldr context <func> --depth 2` |
| L3: CFG | Complexity | `tldr cfg <file> <func>` |
| L4: DFG | Data flow | `tldr dfg <file> <func>` |
| L5: Slice | Dependencies | `tldr slice <file> <func> <line>` |

## Execution

Given a function name, run all layers:

```bash
# First find the file
tldr search "def <function_name>" .

# Then run each layer
tldr extract <found_file>              # L1: Full file structure
tldr context <function_name> --project . --depth 2  # L2: Call graph
tldr cfg <found_file> <function_name>  # L3: Control flow
tldr dfg <found_file> <function_name>  # L4: Data flow
tldr slice <found_file> <function_name> <target_line>  # L5: Slice
```

## Output Format

```
## Deep Analysis: {function_name}

### L1: Structure (AST)
File: {file_path}
Signature: {signature}
Docstring: {docstring}

### L2: Call Graph
Calls: {list of functions this calls}
Called by: {list of functions that call this}

### L3: Control Flow (CFG)
Blocks: {N}
Cyclomatic Complexity: {M}
[Hot if M > 10]
Branches:
  - if: line X
  - for: line Y
  - ...

### L4: Data Flow (DFG)
Variables defined:
  - {var1} @ line X
  - {var2} @ line Y
Variables used:
  - {var1} @ lines [A, B, C]
  - {var2} @ lines [D, E]

### L5: Program Slice (affecting line {target})
Lines in slice: {N}
Key dependencies:
  - line X → line Y (data)
  - line A → line B (control)

---
Total: ~{tokens} tokens (95% savings vs raw file)
```

## When to Use

1. **Debugging** - Need to understand all paths through a function
2. **Refactoring** - Need to know what depends on what
3. **Code review** - Analyzing complex functions
4. **Performance** - Finding hot spots (high cyclomatic complexity)

## Programmatic API

```python
from tldr.api import (
    extract_file,
    get_relevant_context,
    get_cfg_context,
    get_dfg_context,
    get_slice
)

# All layers for one function
file_info = extract_file("src/processor.py")
context = get_relevant_context("src/", "process_data", depth=2)
cfg = get_cfg_context("src/processor.py", "process_data")
dfg = get_dfg_context("src/processor.py", "process_data")
slice_lines = get_slice("src/processor.py", "process_data", target_line=42)
```
